"""
Shared data models and Pydantic schemas used across services.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# Enums
class RecommendationType(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class PositionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class DataProvider(str, Enum):
    ALPHAVANTAGE = "alphavantage"
    FINNHUB = "finnhub"
    POLYGON = "polygon"
    TIINGO = "tiingo"


# Base Models
class BaseDocument(BaseModel):
    """Base model for all Firestore documents."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Data Ingestion Models
class PriceData(BaseDocument):
    """Daily price data model."""
    symbol: str
    date: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    adjusted_close: Optional[Decimal] = None
    provider: DataProvider

    class Config:
        json_encoders = {
            Decimal: float
        }


class IntradayPriceData(BaseDocument):
    """Intraday price data model."""
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: int
    provider: DataProvider

    class Config:
        json_encoders = {
            Decimal: float
        }


class FundamentalData(BaseDocument):
    """Company fundamental data model."""
    symbol: str
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    revenue: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    provider: DataProvider

    class Config:
        json_encoders = {
            Decimal: float
        }


class NewsData(BaseDocument):
    """News data model."""
    headline: str
    summary: str
    url: str
    published_at: datetime
    symbols: List[str] = []
    sentiment_score: Optional[float] = None
    provider: DataProvider


# ML Pipeline Models
class MLRecommendation(BaseDocument):
    """ML model recommendation."""
    symbol: str
    recommendation: RecommendationType
    confidence_score: float = Field(ge=0.0, le=100.0)
    price_target: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    model_version: str
    features_used: Dict[str, Any]

    @validator('confidence_score')
    def validate_confidence(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Confidence score must be between 0 and 100')
        return v

    class Config:
        json_encoders = {
            Decimal: float
        }


class ModelMetadata(BaseDocument):
    """ML model metadata and performance metrics."""
    model_name: str
    model_version: str
    training_date: datetime
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: float
    sharpe_ratio: Optional[float] = None
    hyperparameters: Dict[str, Any]
    feature_importance: Dict[str, float]


# Strategy Engine Models
class TradeSignal(BaseDocument):
    """Trade signal from strategy engine."""
    symbol: str
    signal_type: RecommendationType
    quantity: int
    price_limit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    confidence: float
    reasoning: str
    expires_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            Decimal: float
        }


# Portfolio Models
class Position(BaseDocument):
    """Portfolio position model."""
    symbol: str
    quantity: int
    average_cost: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    status: PositionStatus = PositionStatus.ACTIVE
    opened_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            Decimal: float
        }


class Transaction(BaseDocument):
    """Trade transaction model."""
    symbol: str
    transaction_type: TransactionType
    quantity: int
    price: Decimal
    total_amount: Decimal
    fees: Decimal = Decimal('0.00')
    executed_at: datetime
    order_id: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: float
        }


class WatchlistItem(BaseDocument):
    """Watchlist item model."""
    symbol: str
    added_by: str
    notes: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=5)


# API Response Models
class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Configuration Models
class ServiceConfig(BaseModel):
    """Base service configuration."""
    service_name: str
    project_id: str = "moda-trader"
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8080


class DataIngestionConfig(ServiceConfig):
    """Data ingestion service configuration."""
    api_rate_limit: int = 100  # requests per minute
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay: int = 5  # seconds
