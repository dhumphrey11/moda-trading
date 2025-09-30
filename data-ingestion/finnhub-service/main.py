"""
Finnhub Data Ingestion Service

Fetches financial data from Finnhub API and stores it in Firestore.
Handles:
- Real-time and historical price data
- Company fundamentals
- Company news
- Market news
"""

from shared.models import (
    PriceData, IntradayPriceData, FundamentalData, NewsData,
    DataProvider, HealthCheckResponse, ErrorResponse
)
from shared.logging_config import setup_logging, get_logger
from shared.gcp_secrets import get_finnhub_key
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
setup_logging("finnhub-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Finnhub Data Ingestion Service",
    description="Fetches financial data from Finnhub API",
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
    api_key = get_finnhub_key()

    if not api_key:
        logger.error("Finnhub API key not found")
        raise RuntimeError("Finnhub API key not configured")

    logger.info("Finnhub service started")


class FinnhubClient:
    """Client for Finnhub API."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = get_logger("FinnhubClient")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(self, endpoint: str, params: Dict[str, str] = None) -> Dict[str, Any]:
        """Make API request with error handling."""
        if params is None:
            params = {}
        params["token"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if isinstance(data, dict) and "error" in data:
                raise HTTPException(status_code=400, detail=data["error"])

            return data
        except httpx.HTTPError as e:
            self.logger.error("HTTP error", error=str(
                e), endpoint=endpoint, params=params)
            raise HTTPException(
                status_code=500, detail=f"API request failed: {str(e)}")

    async def get_quote(self, symbol: str) -> Optional[IntradayPriceData]:
        """Get real-time quote for a symbol."""
        data = await self._make_request("quote", {"symbol": symbol})

        if not data or data.get("c") is None:
            return None

        try:
            quote = IntradayPriceData(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(data["t"]),
                price=Decimal(str(data["c"])),
                volume=data.get("v", 0),
                provider=DataProvider.FINNHUB
            )
            return quote
        except (ValueError, KeyError) as e:
            self.logger.error("Error parsing quote data",
                              symbol=symbol, error=str(e))
            return None

    async def get_candles(self, symbol: str, resolution: str = "D",
                          from_date: datetime = None, to_date: datetime = None) -> List[PriceData]:
        """Get candlestick data for a symbol."""
        if from_date is None:
            from_date = datetime.now() - timedelta(days=365)
        if to_date is None:
            to_date = datetime.now()

        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": str(int(from_date.timestamp())),
            "to": str(int(to_date.timestamp()))
        }

        data = await self._make_request("stock/candle", params)

        if data.get("s") != "ok" or not data.get("c"):
            return []

        prices = []
        for i in range(len(data["c"])):
            try:
                price = PriceData(
                    symbol=symbol,
                    date=datetime.fromtimestamp(data["t"][i]),
                    open_price=Decimal(str(data["o"][i])),
                    high_price=Decimal(str(data["h"][i])),
                    low_price=Decimal(str(data["l"][i])),
                    close_price=Decimal(str(data["c"][i])),
                    volume=data["v"][i],
                    provider=DataProvider.FINNHUB
                )
                prices.append(price)
            except (ValueError, KeyError, IndexError) as e:
                self.logger.error("Error parsing candle data",
                                  symbol=symbol, index=i, error=str(e))
                continue

        return prices

    async def get_basic_fundamentals(self, symbol: str) -> Optional[FundamentalData]:
        """Get basic fundamental data for a symbol."""
        data = await self._make_request("stock/metric", {"symbol": symbol, "metric": "all"})

        if not data or "metric" not in data:
            return None

        try:
            metrics = data["metric"]
            fundamental = FundamentalData(
                symbol=symbol,
                # Finnhub doesn't specify fiscal year in basic metrics
                fiscal_year=datetime.now().year,
                pe_ratio=Decimal(str(metrics["peBasicExclExtraTTM"])) if metrics.get(
                    "peBasicExclExtraTTM") else None,
                eps=Decimal(str(metrics["epsBasicExclExtraSharesOutstandingTTM"])) if metrics.get(
                    "epsBasicExclExtraSharesOutstandingTTM") else None,
                roe=Decimal(str(metrics["roeTTM"])) if metrics.get(
                    "roeTTM") else None,
                debt_to_equity=Decimal(str(
                    metrics["totalDebt/totalEquityTTM"])) if metrics.get("totalDebt/totalEquityTTM") else None,
                market_cap=Decimal(str(metrics["marketCapitalization"])) if metrics.get(
                    "marketCapitalization") else None,
                provider=DataProvider.FINNHUB
            )
            return fundamental
        except (ValueError, KeyError) as e:
            self.logger.error("Error parsing fundamental data",
                              symbol=symbol, error=str(e))
            return None

    async def get_company_news(self, symbol: str, from_date: datetime = None,
                               to_date: datetime = None) -> List[NewsData]:
        """Get company-specific news."""
        if from_date is None:
            from_date = datetime.now() - timedelta(days=7)
        if to_date is None:
            to_date = datetime.now()

        params = {
            "symbol": symbol,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d")
        }

        data = await self._make_request("company-news", params)

        if not isinstance(data, list):
            return []

        news_items = []
        for item in data:
            try:
                news = NewsData(
                    headline=item["headline"],
                    summary=item.get("summary", ""),
                    url=item["url"],
                    published_at=datetime.fromtimestamp(item["datetime"]),
                    symbols=[symbol],
                    provider=DataProvider.FINNHUB
                )
                news_items.append(news)
            except (ValueError, KeyError) as e:
                self.logger.error("Error parsing news data", error=str(e))
                continue

        return news_items

    async def get_market_news(self, category: str = "general") -> List[NewsData]:
        """Get general market news."""
        params = {"category": category}
        data = await self._make_request("news", params)

        if not isinstance(data, list):
            return []

        news_items = []
        for item in data:
            try:
                news = NewsData(
                    headline=item["headline"],
                    summary=item.get("summary", ""),
                    url=item["url"],
                    published_at=datetime.fromtimestamp(item["datetime"]),
                    symbols=[],  # Market news doesn't have specific symbols
                    provider=DataProvider.FINNHUB
                )
                news_items.append(news)
            except (ValueError, KeyError) as e:
                self.logger.error(
                    "Error parsing market news data", error=str(e))
                continue

        return news_items


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="finnhub-service")


@app.post("/ingest/quote/{symbol}")
async def ingest_quote(symbol: str, background_tasks: BackgroundTasks):
    """Ingest real-time quote for a symbol."""
    background_tasks.add_task(fetch_and_store_quote, symbol)
    return {"message": f"Quote ingestion started for {symbol}"}


@app.post("/ingest/daily-prices/{symbol}")
async def ingest_daily_prices(symbol: str, background_tasks: BackgroundTasks):
    """Ingest daily price data for a symbol."""
    background_tasks.add_task(fetch_and_store_daily_prices, symbol)
    return {"message": f"Daily price ingestion started for {symbol}"}


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


@app.post("/ingest/market-news")
async def ingest_market_news(background_tasks: BackgroundTasks, category: str = "general"):
    """Ingest general market news."""
    background_tasks.add_task(fetch_and_store_market_news, category)
    return {"message": f"Market news ingestion started for category: {category}"}


# Background tasks
async def fetch_and_store_quote(symbol: str):
    """Fetch and store real-time quote."""
    client = FinnhubClient(api_key)

    try:
        quote = await client.get_quote(symbol)

        if quote:
            document_id = f"{symbol}_{quote.timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "di_prices_intraday",
                document_id,
                quote.dict()
            )
            logger.info("Quote stored", symbol=symbol)
    except Exception as e:
        logger.error("Failed to fetch quote", symbol=symbol, error=str(e))
    finally:
        await client.close()


async def fetch_and_store_daily_prices(symbol: str):
    """Fetch and store daily price data."""
    client = FinnhubClient(api_key)

    try:
        prices = await client.get_candles(symbol, resolution="D")

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


async def fetch_and_store_fundamentals(symbol: str):
    """Fetch and store fundamental data."""
    client = FinnhubClient(api_key)

    try:
        fundamental = await client.get_basic_fundamentals(symbol)

        if fundamental:
            document_id = f"{symbol}_{datetime.now().strftime('%Y-%m-%d')}"
            await firestore_client.upsert_document(
                "di_fundamentals",
                document_id,
                fundamental.dict()
            )
            logger.info("Fundamental data stored", symbol=symbol)
    except Exception as e:
        logger.error("Failed to fetch fundamental data",
                     symbol=symbol, error=str(e))
    finally:
        await client.close()


async def fetch_and_store_company_news(symbol: str):
    """Fetch and store company news."""
    client = FinnhubClient(api_key)

    try:
        news_items = await client.get_company_news(symbol)

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


async def fetch_and_store_market_news(category: str):
    """Fetch and store market news."""
    client = FinnhubClient(api_key)

    try:
        news_items = await client.get_market_news(category)

        # Store in Firestore
        for news in news_items:
            document_id = f"market_{news.published_at.strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "di_market_news",
                document_id,
                news.dict()
            )

        logger.info("Market news stored", category=category,
                    count=len(news_items))
    except Exception as e:
        logger.error("Failed to fetch market news",
                     category=category, error=str(e))
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
