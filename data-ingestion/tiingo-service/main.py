"""
Tiingo Data Ingestion Service

Fetches financial data from Tiingo API and stores it in Firestore.
Handles:
- Daily and intraday price data
- Company fundamentals
- Company and market news
"""

from shared.models import (
    PriceData, IntradayPriceData, FundamentalData, NewsData,
    DataProvider, HealthCheckResponse, ErrorResponse
)
from shared.logging_config import setup_logging, get_logger
from shared.gcp_secrets import get_tiingo_key
from shared.firestore_client import FirestoreClient
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Add parent directory to path for shared imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Setup logging
setup_logging("tiingo-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Tiingo Data Ingestion Service",
    description="Fetches financial data from Tiingo API",
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
    api_key = get_tiingo_key()

    if not api_key:
        logger.error("Tiingo API key not found")
        raise RuntimeError("Tiingo API key not configured")

    logger.info("Tiingo service started")


class TiingoClient:
    """Client for Tiingo API."""

    BASE_URL = "https://api.tiingo.com/tiingo"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = get_logger("TiingoClient")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(self, endpoint: str, params: Dict[str, str] = None) -> Any:
        """Make API request with error handling."""
        if params is None:
            params = {}

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if isinstance(data, dict) and "detail" in data:
                raise HTTPException(status_code=400, detail=data["detail"])

            return data
        except httpx.HTTPError as e:
            self.logger.error("HTTP error", error=str(
                e), endpoint=endpoint, params=params)
            raise HTTPException(
                status_code=500, detail=f"API request failed: {str(e)}")

    async def get_daily_prices(self, symbol: str, start_date: datetime = None,
                               end_date: datetime = None) -> List[PriceData]:
        """Get daily price data for a symbol."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()

        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "format": "json"
        }

        endpoint = f"daily/{symbol}/prices"
        data = await self._make_request(endpoint, params)

        if not isinstance(data, list):
            return []

        prices = []
        for item in data:
            try:
                price = PriceData(
                    symbol=symbol,
                    date=datetime.fromisoformat(
                        item["date"].replace("Z", "+00:00")),
                    open_price=Decimal(str(item["open"])),
                    high_price=Decimal(str(item["high"])),
                    low_price=Decimal(str(item["low"])),
                    close_price=Decimal(str(item["close"])),
                    adjusted_close=Decimal(str(item["adjClose"])),
                    volume=item["volume"],
                    provider=DataProvider.TIINGO
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing price data",
                                  symbol=symbol, error=str(e))
                continue

        return prices

    async def get_intraday_prices(self, symbol: str, date: datetime = None) -> List[IntradayPriceData]:
        """Get intraday price data for a symbol."""
        if date is None:
            date = datetime.now()

        params = {
            "startDate": date.strftime("%Y-%m-%d"),
            "endDate": date.strftime("%Y-%m-%d"),
            "resampleFreq": "5min",
            "format": "json"
        }

        endpoint = f"iex/{symbol}/prices"
        data = await self._make_request(endpoint, params)

        if not isinstance(data, list):
            return []

        prices = []
        for item in data:
            try:
                price = IntradayPriceData(
                    symbol=symbol,
                    timestamp=datetime.fromisoformat(
                        item["date"].replace("Z", "+00:00")),
                    price=Decimal(str(item["close"])),
                    volume=item.get("volume", 0),
                    provider=DataProvider.TIINGO
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing intraday data",
                                  symbol=symbol, error=str(e))
                continue

        return prices

    async def get_company_metadata(self, symbol: str) -> Optional[FundamentalData]:
        """Get company metadata."""
        endpoint = f"daily/{symbol}"
        data = await self._make_request(endpoint)

        if not isinstance(data, dict):
            return None

        try:
            fundamental = FundamentalData(
                symbol=symbol,
                # Tiingo metadata doesn't include fiscal year details
                fiscal_year=datetime.now().year,
                provider=DataProvider.TIINGO
            )
            return fundamental
        except (ValueError, KeyError) as e:
            self.logger.error("Error parsing company metadata",
                              symbol=symbol, error=str(e))
            return None

    async def get_news(self, symbols: List[str] = None, limit: int = 50) -> List[NewsData]:
        """Get news articles."""
        params = {
            "limit": str(limit),
            "sortBy": "publishedDate"
        }

        if symbols:
            params["tickers"] = ",".join(symbols)

        # Use news API endpoint
        url = "https://api.tiingo.com/tiingo/news"
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                return []

            news_items = []
            for item in data:
                try:
                    news = NewsData(
                        headline=item["title"],
                        summary=item.get("description", ""),
                        url=item["url"],
                        published_at=datetime.fromisoformat(
                            item["publishedDate"].replace("Z", "+00:00")),
                        symbols=item.get("tickers", []),
                        provider=DataProvider.TIINGO
                    )
                    news_items.append(news)
                except (ValueError, KeyError) as e:
                    self.logger.error("Error parsing news data", error=str(e))
                    continue

            return news_items

        except Exception as e:
            self.logger.error("Error fetching news", error=str(e))
            return []


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="tiingo-service")


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


@app.post("/ingest/news")
async def ingest_news(background_tasks: BackgroundTasks, symbols: List[str] = None):
    """Ingest news data."""
    background_tasks.add_task(fetch_and_store_news, symbols)
    return {"message": "News ingestion started"}


# Background tasks
async def fetch_and_store_daily_prices(symbol: str):
    """Fetch and store daily price data."""
    client = TiingoClient(api_key)

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
    client = TiingoClient(api_key)

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
    client = TiingoClient(api_key)

    try:
        fundamental = await client.get_company_metadata(symbol)

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


async def fetch_and_store_news(symbols: List[str] = None):
    """Fetch and store news data."""
    client = TiingoClient(api_key)

    try:
        news_items = await client.get_news(symbols)

        # Store in Firestore
        collection = "di_company_news" if symbols else "di_market_news"

        for news in news_items:
            document_id = f"tiingo_{news.published_at.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                collection,
                document_id,
                news.dict()
            )

        logger.info("News stored", symbols=symbols, count=len(news_items))
    except Exception as e:
        logger.error("Failed to fetch news", symbols=symbols, error=str(e))
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
