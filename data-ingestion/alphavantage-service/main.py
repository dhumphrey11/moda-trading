"""
Alpha Vantage Data Ingestion Service

Fetches financial data from Alpha Vantage API and stores it in Firestore.
Handles:
- Daily and intraday price data
- Company fundamentals
- Company news
"""

from shared.models import (
    PriceData, IntradayPriceData, FundamentalData, NewsData,
    DataProvider, HealthCheckResponse, ErrorResponse
)
from shared.logging_config import setup_logging, get_logger
from shared.gcp_secrets import get_alphavantage_key
from shared.firestore_client import FirestoreClient
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx
import pandas as pd

# Add parent directory to path for shared imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Setup logging
setup_logging("alphavantage-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Alpha Vantage Data Ingestion Service",
    description="Fetches financial data from Alpha Vantage API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients
firestore_client = None
api_key = None


@app.on_event("startup")
async def startup_event():
    """Initialize clients on startup."""
    global firestore_client, api_key

    firestore_client = FirestoreClient()
    api_key = get_alphavantage_key()

    if not api_key:
        logger.error("Alpha Vantage API key not found")
        raise RuntimeError("Alpha Vantage API key not configured")

    logger.info("Alpha Vantage service started")


class AlphaVantageClient:
    """Client for Alpha Vantage API."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = get_logger("AlphaVantageClient")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make API request with error handling."""
        params["apikey"] = self.api_key

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "Error Message" in data:
                raise HTTPException(
                    status_code=400, detail=data["Error Message"])
            if "Note" in data:
                raise HTTPException(
                    status_code=429, detail="API rate limit exceeded")

            return data
        except httpx.HTTPError as e:
            self.logger.error("HTTP error", error=str(e), params=params)
            raise HTTPException(
                status_code=500, detail=f"API request failed: {str(e)}")

    async def get_daily_prices(self, symbol: str, outputsize: str = "compact") -> List[PriceData]:
        """Get daily price data for a symbol."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize
        }

        data = await self._make_request(params)
        time_series = data.get("Time Series (Daily)", {})

        prices = []
        for date_str, price_data in time_series.items():
            try:
                price = PriceData(
                    symbol=symbol,
                    date=datetime.strptime(date_str, "%Y-%m-%d"),
                    open_price=Decimal(price_data["1. open"]),
                    high_price=Decimal(price_data["2. high"]),
                    low_price=Decimal(price_data["3. low"]),
                    close_price=Decimal(price_data["4. close"]),
                    adjusted_close=Decimal(price_data["5. adjusted close"]),
                    volume=int(price_data["6. volume"]),
                    provider=DataProvider.ALPHAVANTAGE
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing price data",
                                  symbol=symbol, date=date_str, error=str(e))
                continue

        return prices

    async def get_intraday_prices(self, symbol: str, interval: str = "5min") -> List[IntradayPriceData]:
        """Get intraday price data for a symbol."""
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "outputsize": "compact"
        }

        data = await self._make_request(params)
        time_series = data.get(f"Time Series ({interval})", {})

        prices = []
        for timestamp_str, price_data in time_series.items():
            try:
                price = IntradayPriceData(
                    symbol=symbol,
                    timestamp=datetime.strptime(
                        timestamp_str, "%Y-%m-%d %H:%M:%S"),
                    price=Decimal(price_data["4. close"]),
                    volume=int(price_data["5. volume"]),
                    provider=DataProvider.ALPHAVANTAGE
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing intraday data",
                                  symbol=symbol, timestamp=timestamp_str, error=str(e))
                continue

        return prices

    async def get_company_overview(self, symbol: str) -> Optional[FundamentalData]:
        """Get company overview and fundamental data."""
        params = {
            "function": "OVERVIEW",
            "symbol": symbol
        }

        data = await self._make_request(params)

        if not data or data.get("Symbol") != symbol:
            return None

        try:
            fundamental = FundamentalData(
                symbol=symbol,
                fiscal_year=int(data.get("FiscalYearEnd", "0")[
                                :4]) if data.get("FiscalYearEnd") else None,
                revenue=Decimal(data["RevenueTTM"]) if data.get(
                    "RevenueTTM") and data["RevenueTTM"] != "None" else None,
                net_income=Decimal(data["QuarterlyEarningsGrowthYOY"]) if data.get(
                    "QuarterlyEarningsGrowthYOY") and data["QuarterlyEarningsGrowthYOY"] != "None" else None,
                eps=Decimal(data["EPS"]) if data.get(
                    "EPS") and data["EPS"] != "None" else None,
                pe_ratio=Decimal(data["PERatio"]) if data.get(
                    "PERatio") and data["PERatio"] != "None" else None,
                market_cap=Decimal(data["MarketCapitalization"]) if data.get(
                    "MarketCapitalization") and data["MarketCapitalization"] != "None" else None,
                provider=DataProvider.ALPHAVANTAGE
            )
            return fundamental
        except (ValueError, KeyError) as e:
            self.logger.error("Error parsing fundamental data",
                              symbol=symbol, error=str(e))
            return None

    async def get_company_news(self, symbol: str, limit: int = 50) -> List[NewsData]:
        """Get company news (Alpha Vantage doesn't have dedicated news endpoint, placeholder)."""
        # Alpha Vantage doesn't have a dedicated news endpoint in the free tier
        # This would need to be implemented with a paid plan or different provider
        return []


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="alphavantage-service")


@app.post("/ingest/daily-prices/{symbol}")
async def ingest_daily_prices(symbol: str, background_tasks: BackgroundTasks):
    """Ingest daily price data for a symbol."""
    background_tasks.add_task(fetch_and_store_daily_prices, symbol)
    return {"message": f"Daily price ingestion started for {symbol}"}


@app.post("/ingest/intraday-prices/{symbol}")
async def ingest_intraday_prices(symbol: str, background_tasks: BackgroundTasks):
    """Ingest intraday price data for a symbol."""
    background_tasks.add_task(fetch_and_store_intraday_prices, symbol)
    return {"message": f"Intraday price ingestion started for {symbol}"}


@app.post("/ingest/fundamentals/{symbol}")
async def ingest_fundamentals(symbol: str, background_tasks: BackgroundTasks):
    """Ingest fundamental data for a symbol."""
    background_tasks.add_task(fetch_and_store_fundamentals, symbol)
    return {"message": f"Fundamental data ingestion started for {symbol}"}


@app.post("/ingest/batch-daily")
async def ingest_batch_daily(symbols: List[str], background_tasks: BackgroundTasks):
    """Ingest daily prices for multiple symbols."""
    for symbol in symbols:
        background_tasks.add_task(fetch_and_store_daily_prices, symbol)
    return {"message": f"Batch daily price ingestion started for {len(symbols)} symbols"}


# Background tasks
async def fetch_and_store_daily_prices(symbol: str):
    """Fetch and store daily price data."""
    client = AlphaVantageClient(api_key)

    try:
        prices = await client.get_daily_prices(symbol)

        # Store in Firestore
        for price in prices:
            document_id = f"{symbol}_{price.date.strftime('%Y-%m-%d')}"
            await firestore_client.upsert_document(
                "di_prices_daily",
                document_id,
                price.dict()
            )

        logger.info("Daily prices stored", symbol=symbol, count=len(prices))
    except Exception as e:
        logger.error("Failed to fetch daily prices",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


async def fetch_and_store_intraday_prices(symbol: str):
    """Fetch and store intraday price data."""
    client = AlphaVantageClient(api_key)

    try:
        prices = await client.get_intraday_prices(symbol)

        # Store in Firestore
        for price in prices:
            document_id = f"{symbol}_{price.timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "di_prices_intraday",
                document_id,
                price.dict()
            )

        logger.info("Intraday prices stored", symbol=symbol, count=len(prices))
    except Exception as e:
        logger.error("Failed to fetch intraday prices",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


async def fetch_and_store_fundamentals(symbol: str):
    """Fetch and store fundamental data."""
    client = AlphaVantageClient(api_key)

    try:
        fundamental = await client.get_company_overview(symbol)

        if fundamental:
            document_id = f"{symbol}_{datetime.now().strftime('%Y-%m-%d')}"
            await firestore_client.upsert_document(
                "di_fundamentals",
                document_id,
                fundamental.dict()
            )
            logger.info("Fundamental data stored", symbol=symbol)
        else:
            logger.warning("No fundamental data found", symbol=symbol)
    except Exception as e:
        logger.error("Failed to fetch fundamental data",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
