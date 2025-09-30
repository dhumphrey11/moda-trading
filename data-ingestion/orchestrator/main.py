"""
Data Ingestion Orchestrator Service

Coordinates data collection from multiple sources based on:
- Active positions (frequent intraday updates)
- Watchlist symbols (daily prices, monthly fundamentals)
- Market news (regular intervals)

Optimizes API calls to stay within free tier limits.
"""

from shared.models import HealthCheckResponse, ErrorResponse
from shared.logging_config import setup_logging, get_logger
from shared.firestore_client import FirestoreClient
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
from google.cloud import pubsub_v1

# Add parent directory to path for shared imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Setup logging
setup_logging("orchestrator-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Data Ingestion Orchestrator",
    description="Coordinates data collection from multiple financial data sources",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskType(str, Enum):
    INTRADAY_PRICES = "intraday_prices"
    DAILY_PRICES = "daily_prices"
    FUNDAMENTALS = "fundamentals"
    COMPANY_NEWS = "company_news"
    MARKET_NEWS = "market_news"


class DataProvider(str, Enum):
    ALPHAVANTAGE = "alphavantage"
    FINNHUB = "finnhub"
    POLYGON = "polygon"
    TIINGO = "tiingo"


# Service URLs (update these based on your deployment)
SERVICE_URLS = {
    DataProvider.ALPHAVANTAGE: "http://alphavantage-service:8080",
    DataProvider.FINNHUB: "http://finnhub-service:8080",
    DataProvider.POLYGON: "http://polygon-service:8080",
    DataProvider.TIINGO: "http://tiingo-service:8080"
}

# Global clients
firestore_client = None
publisher = None
http_client = None


@app.on_event("startup")
async def startup_event():
    """Initialize clients on startup."""
    global firestore_client, publisher, http_client

    firestore_client = FirestoreClient()
    publisher = pubsub_v1.PublisherClient()
    http_client = httpx.AsyncClient(timeout=60.0)

    logger.info("Orchestrator service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up clients on shutdown."""
    global http_client
    if http_client:
        await http_client.aclose()


class OrchestrationEngine:
    """Main orchestration engine for data ingestion."""

    def __init__(self):
        self.logger = get_logger("OrchestrationEngine")
        self.api_call_counts = {}  # Track API calls per provider
        self.last_reset = datetime.now()

    def reset_api_counters_if_needed(self):
        """Reset API call counters daily."""
        now = datetime.now()
        if (now - self.last_reset).days >= 1:
            self.api_call_counts = {}
            self.last_reset = now
            self.logger.info("API call counters reset")

    def can_make_api_call(self, provider: DataProvider, task_type: TaskType) -> bool:
        """Check if we can make an API call without exceeding limits."""
        self.reset_api_counters_if_needed()

        # Free tier limits (conservative estimates)
        DAILY_LIMITS = {
            DataProvider.ALPHAVANTAGE: 100,  # 5 calls per minute, ~500/day conservative
            DataProvider.FINNHUB: 250,      # 60 calls per minute on free tier
            DataProvider.POLYGON: 100,      # 5 calls per minute on free tier
            DataProvider.TIINGO: 500        # 1000 calls per day on free tier
        }

        provider_key = provider.value
        current_count = self.api_call_counts.get(provider_key, 0)
        limit = DAILY_LIMITS.get(provider, 100)

        return current_count < limit

    def increment_api_call_count(self, provider: DataProvider):
        """Increment API call count for a provider."""
        provider_key = provider.value
        self.api_call_counts[provider_key] = self.api_call_counts.get(
            provider_key, 0) + 1

    async def get_active_positions(self) -> List[str]:
        """Get list of symbols from active positions."""
        try:
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("status", "==", "active")]
            )
            return [pos["symbol"] for pos in positions]
        except Exception as e:
            self.logger.error("Failed to get active positions", error=str(e))
            return []

    async def get_watchlist_symbols(self) -> List[str]:
        """Get list of symbols from watchlist."""
        try:
            watchlist = await firestore_client.query_documents("pf_watchlist")
            return [item["symbol"] for item in watchlist]
        except Exception as e:
            self.logger.error("Failed to get watchlist symbols", error=str(e))
            return []

    async def call_service_endpoint(self, provider: DataProvider, endpoint: str,
                                    symbol: str = None) -> bool:
        """Call a specific service endpoint."""
        if not self.can_make_api_call(provider, TaskType.DAILY_PRICES):
            self.logger.warning("API limit reached", provider=provider.value)
            return False

        try:
            base_url = SERVICE_URLS.get(provider)
            if not base_url:
                self.logger.error("Service URL not configured",
                                  provider=provider.value)
                return False

            url = f"{base_url}/{endpoint}"
            if symbol:
                url = url.replace("{symbol}", symbol)

            response = await http_client.post(url)
            response.raise_for_status()

            self.increment_api_call_count(provider)
            self.logger.info("Service endpoint called",
                             provider=provider.value, endpoint=endpoint, symbol=symbol)
            return True

        except Exception as e:
            self.logger.error("Failed to call service endpoint",
                              provider=provider.value, endpoint=endpoint, symbol=symbol, error=str(e))
            return False

    async def orchestrate_intraday_data_collection(self):
        """Collect intraday data for active positions."""
        active_symbols = await self.get_active_positions()

        if not active_symbols:
            self.logger.info("No active positions found")
            return

        self.logger.info("Starting intraday data collection",
                         symbols_count=len(active_symbols))

        # Distribute symbols across providers to balance load
        providers = [DataProvider.FINNHUB, DataProvider.ALPHAVANTAGE]

        for i, symbol in enumerate(active_symbols):
            provider = providers[i % len(providers)]

            # Get real-time quotes
            if provider == DataProvider.FINNHUB:
                await self.call_service_endpoint(provider, "ingest/quote/{symbol}", symbol)
            elif provider == DataProvider.ALPHAVANTAGE:
                await self.call_service_endpoint(provider, "ingest/intraday-prices/{symbol}", symbol)

            # Get company news
            await self.call_service_endpoint(provider, "ingest/company-news/{symbol}", symbol)

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

    async def orchestrate_daily_data_collection(self):
        """Collect daily data for watchlist symbols."""
        watchlist_symbols = await self.get_watchlist_symbols()
        active_symbols = await self.get_active_positions()

        # Combine and deduplicate
        all_symbols = list(set(watchlist_symbols + active_symbols))

        if not all_symbols:
            self.logger.info("No symbols found for daily collection")
            return

        self.logger.info("Starting daily data collection",
                         symbols_count=len(all_symbols))

        # Distribute symbols across providers
        providers = [DataProvider.ALPHAVANTAGE, DataProvider.FINNHUB,
                     DataProvider.POLYGON, DataProvider.TIINGO]

        for i, symbol in enumerate(all_symbols):
            provider = providers[i % len(providers)]

            # Get daily prices
            await self.call_service_endpoint(provider, "ingest/daily-prices/{symbol}", symbol)

            # Small delay to avoid rate limiting
            await asyncio.sleep(1.0)

    async def orchestrate_fundamental_data_collection(self):
        """Collect fundamental data (monthly for watchlist)."""
        watchlist_symbols = await self.get_watchlist_symbols()

        if not watchlist_symbols:
            self.logger.info(
                "No watchlist symbols found for fundamental collection")
            return

        self.logger.info("Starting fundamental data collection",
                         symbols_count=len(watchlist_symbols))

        # Use providers that have good fundamental data
        providers = [DataProvider.ALPHAVANTAGE, DataProvider.FINNHUB]

        for i, symbol in enumerate(watchlist_symbols):
            provider = providers[i % len(providers)]

            await self.call_service_endpoint(provider, "ingest/fundamentals/{symbol}", symbol)

            # Longer delay for fundamental data
            await asyncio.sleep(2.0)

    async def orchestrate_market_news_collection(self):
        """Collect general market news."""
        self.logger.info("Starting market news collection")

        # Use providers that have good news coverage
        providers = [DataProvider.FINNHUB]

        for provider in providers:
            if provider == DataProvider.FINNHUB:
                await self.call_service_endpoint(provider, "ingest/market-news")

            await asyncio.sleep(1.0)

    async def get_orchestration_status(self) -> Dict[str, Any]:
        """Get current orchestration status."""
        active_symbols = await self.get_active_positions()
        watchlist_symbols = await self.get_watchlist_symbols()

        return {
            "active_positions_count": len(active_symbols),
            "watchlist_count": len(watchlist_symbols),
            "api_call_counts": self.api_call_counts,
            "last_counter_reset": self.last_reset.isoformat(),
            "service_urls": SERVICE_URLS
        }


# Global orchestrator instance
orchestrator = OrchestrationEngine()


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="orchestrator-service")


@app.get("/status")
async def get_status():
    """Get orchestration status."""
    return await orchestrator.get_orchestration_status()


@app.post("/orchestrate/intraday")
async def orchestrate_intraday(background_tasks: BackgroundTasks):
    """Trigger intraday data collection."""
    background_tasks.add_task(
        orchestrator.orchestrate_intraday_data_collection)
    return {"message": "Intraday data collection started"}


@app.post("/orchestrate/daily")
async def orchestrate_daily(background_tasks: BackgroundTasks):
    """Trigger daily data collection."""
    background_tasks.add_task(orchestrator.orchestrate_daily_data_collection)
    return {"message": "Daily data collection started"}


@app.post("/orchestrate/fundamentals")
async def orchestrate_fundamentals(background_tasks: BackgroundTasks):
    """Trigger fundamental data collection."""
    background_tasks.add_task(
        orchestrator.orchestrate_fundamental_data_collection)
    return {"message": "Fundamental data collection started"}


@app.post("/orchestrate/market-news")
async def orchestrate_market_news(background_tasks: BackgroundTasks):
    """Trigger market news collection."""
    background_tasks.add_task(orchestrator.orchestrate_market_news_collection)
    return {"message": "Market news collection started"}


@app.post("/orchestrate/full")
async def orchestrate_full_collection(background_tasks: BackgroundTasks):
    """Trigger full data collection cycle."""
    background_tasks.add_task(run_full_collection_cycle)
    return {"message": "Full data collection cycle started"}


# Background tasks
async def run_full_collection_cycle():
    """Run a complete data collection cycle."""
    logger.info("Starting full collection cycle")

    try:
        # Market news (independent of symbols)
        await orchestrator.orchestrate_market_news_collection()
        await asyncio.sleep(5)

        # Intraday data for active positions
        await orchestrator.orchestrate_intraday_data_collection()
        await asyncio.sleep(10)

        # Daily data for all symbols
        await orchestrator.orchestrate_daily_data_collection()
        await asyncio.sleep(10)

        # Fundamental data (less frequent)
        current_hour = datetime.now().hour
        if current_hour in [9, 15]:  # Run twice a day
            await orchestrator.orchestrate_fundamental_data_collection()

        logger.info("Full collection cycle completed")

    except Exception as e:
        logger.error("Error in full collection cycle", error=str(e))


# Pub/Sub message handler for Cloud Scheduler integration
@app.post("/pubsub/intraday")
async def handle_intraday_schedule(background_tasks: BackgroundTasks):
    """Handle intraday collection triggered by Cloud Scheduler."""
    background_tasks.add_task(
        orchestrator.orchestrate_intraday_data_collection)
    return {"message": "Intraday collection scheduled"}


@app.post("/pubsub/daily")
async def handle_daily_schedule(background_tasks: BackgroundTasks):
    """Handle daily collection triggered by Cloud Scheduler."""
    background_tasks.add_task(orchestrator.orchestrate_daily_data_collection)
    return {"message": "Daily collection scheduled"}


@app.post("/pubsub/weekly")
async def handle_weekly_schedule(background_tasks: BackgroundTasks):
    """Handle weekly fundamental collection triggered by Cloud Scheduler."""
    background_tasks.add_task(
        orchestrator.orchestrate_fundamental_data_collection)
    return {"message": "Weekly collection scheduled"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
