"""
Polygon.io Data Ingestion Service

Fetches financial data from Polygon.io API and stores it in Firestore.
Handles:
- Real-time and historical price data
- Company fundamentals
- Market news
"""

from shared.models import (
    PriceData, IntradayPriceData, FundamentalData, NewsData,
    DataProvider, HealthCheckResponse, ErrorResponse
)
from shared.logging_config import setup_logging, get_logger
from shared.gcp_secrets import get_polygon_key
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
setup_logging("polygon-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Polygon.io Data Ingestion Service",
    description="Fetches financial data from Polygon.io API",
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
    api_key = get_polygon_key()

    if not api_key:
        logger.error("Polygon API key not found")
        raise RuntimeError("Polygon API key not configured")

    logger.info("Polygon service started")


class PolygonClient:
    """Client for Polygon.io API."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = get_logger("PolygonClient")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(self, endpoint: str, params: Dict[str, str] = None) -> Dict[str, Any]:
        """Make API request with error handling."""
        if params is None:
            params = {}
        params["apikey"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if data.get("status") == "ERROR":
                raise HTTPException(
                    status_code=400, detail=data.get("error", "API error"))

            return data
        except httpx.HTTPError as e:
            self.logger.error("HTTP error", error=str(
                e), endpoint=endpoint, params=params)
            raise HTTPException(
                status_code=500, detail=f"API request failed: {str(e)}")

    async def get_daily_bars(self, symbol: str, from_date: datetime = None,
                             to_date: datetime = None) -> List[PriceData]:
        """Get daily price bars for a symbol."""
        if from_date is None:
            from_date = datetime.now() - timedelta(days=365)
        if to_date is None:
            to_date = datetime.now()

        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        endpoint = f"v2/aggs/ticker/{symbol}/range/1/day/{from_str}/{to_str}"
        data = await self._make_request(endpoint)

        if not data.get("results"):
            return []

        prices = []
        for bar in data["results"]:
            try:
                price = PriceData(
                    symbol=symbol,
                    # Polygon uses milliseconds
                    date=datetime.fromtimestamp(bar["t"] / 1000),
                    open_price=Decimal(str(bar["o"])),
                    high_price=Decimal(str(bar["h"])),
                    low_price=Decimal(str(bar["l"])),
                    close_price=Decimal(str(bar["c"])),
                    volume=bar["v"],
                    provider=DataProvider.POLYGON
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing bar data",
                                  symbol=symbol, error=str(e))
                continue

        return prices

    async def get_minute_bars(self, symbol: str, date: datetime = None) -> List[IntradayPriceData]:
        """Get minute-level price bars for a symbol."""
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        endpoint = f"v2/aggs/ticker/{symbol}/range/1/minute/{date_str}/{date_str}"
        data = await self._make_request(endpoint)

        if not data.get("results"):
            return []

        prices = []
        for bar in data["results"]:
            try:
                price = IntradayPriceData(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(bar["t"] / 1000),
                    price=Decimal(str(bar["c"])),
                    volume=bar["v"],
                    provider=DataProvider.POLYGON
                )
                prices.append(price)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing minute bar data",
                                  symbol=symbol, error=str(e))
                continue

        return prices

    async def get_ticker_details(self, symbol: str) -> Optional[FundamentalData]:
        """Get ticker details and fundamental data."""
        endpoint = f"v3/reference/tickers/{symbol}"
        data = await self._make_request(endpoint)

        if not data.get("results"):
            return None

        try:
            ticker_data = data["results"]

            fundamental = FundamentalData(
                symbol=symbol,
                # Polygon doesn't provide specific fiscal year in basic call
                fiscal_year=datetime.now().year,
                market_cap=Decimal(str(ticker_data.get("market_cap", 0))) if ticker_data.get(
                    "market_cap") else None,
                provider=DataProvider.POLYGON
            )
            return fundamental
        except (ValueError, KeyError) as e:
            self.logger.error("Error parsing ticker details",
                              symbol=symbol, error=str(e))
            return None

    async def get_ticker_news(self, symbol: str, limit: int = 50) -> List[NewsData]:
        """Get news for a specific ticker."""
        params = {
            "ticker": symbol,
            "limit": str(limit)
        }

        data = await self._make_request("v2/reference/news", params)

        if not data.get("results"):
            return []

        news_items = []
        for item in data["results"]:
            try:
                # Parse published date
                published_str = item.get("published_utc", "")
                if published_str:
                    published_at = datetime.fromisoformat(
                        published_str.replace("Z", "+00:00"))
                else:
                    published_at = datetime.now()

                news = NewsData(
                    headline=item["title"],
                    summary=item.get("description", ""),
                    url=item["article_url"],
                    published_at=published_at,
                    symbols=item.get("tickers", [symbol]),
                    provider=DataProvider.POLYGON
                )
                news_items.append(news)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing news data", error=str(e))
                continue

        return news_items


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="polygon-service")


@app.post("/ingest/daily-prices/{symbol}")
async def ingest_daily_prices(symbol: str, background_tasks: BackgroundTasks):
    """Ingest daily price data for a symbol."""
    background_tasks.add_task(fetch_and_store_daily_prices, symbol)
    return {"message": f"Daily price ingestion started for {symbol}"}


@app.post("/ingest/minute-prices/{symbol}")
async def ingest_minute_prices(symbol: str, background_tasks: BackgroundTasks):
    """Ingest minute-level price data for a symbol."""
    background_tasks.add_task(fetch_and_store_minute_prices, symbol)
    return {"message": f"Minute price ingestion started for {symbol}"}


@app.post("/ingest/fundamentals/{symbol}")
async def ingest_fundamentals(symbol: str, background_tasks: BackgroundTasks):
    """Ingest fundamental data for a symbol."""
    background_tasks.add_task(fetch_and_store_fundamentals, symbol)
    return {"message": f"Fundamental data ingestion started for {symbol}"}


@app.post("/ingest/company-news/{symbol}")
async def ingest_company_news(symbol: str, background_tasks: BackgroundTasks):
    """Ingest company news for a symbol."""
    background_tasks.add_task(fetch_and_store_company_news, symbol)
    return {"message": f"Company news ingestion started for {symbol}"}


# Background tasks
async def fetch_and_store_daily_prices(symbol: str):
    """Fetch and store daily price data."""
    client = PolygonClient(api_key)

    try:
        prices = await client.get_daily_bars(symbol)

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


async def fetch_and_store_minute_prices(symbol: str):
    """Fetch and store minute-level price data."""
    client = PolygonClient(api_key)

    try:
        prices = await client.get_minute_bars(symbol)

        # Store in Firestore
        for price in prices:
            document_id = f"{symbol}_{price.timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "di_prices_intraday",
                document_id,
                price.dict()
            )

        logger.info("Minute prices stored", symbol=symbol, count=len(prices))
    except Exception as e:
        logger.error("Failed to fetch minute prices",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


async def fetch_and_store_fundamentals(symbol: str):
    """Fetch and store fundamental data."""
    client = PolygonClient(api_key)

    try:
        fundamental = await client.get_ticker_details(symbol)

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


async def fetch_and_store_company_news(symbol: str):
    """Fetch and store company news."""
    client = PolygonClient(api_key)

    try:
        news_items = await client.get_ticker_news(symbol)

        # Store in Firestore
        for news in news_items:
            document_id = f"{symbol}_{news.published_at.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "di_company_news",
                document_id,
                news.dict()
            )

        logger.info("Company news stored",
                    symbol=symbol, count=len(news_items))
    except Exception as e:
        logger.error("Failed to fetch company news",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
