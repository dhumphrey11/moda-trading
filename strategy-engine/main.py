"""
Strategy Engine Service

Combines ML outputs with rule-based filters to generate actionable trade signals.
Handles:
- Portfolio allocation rules
- Risk management (stop-loss, max drawdown)  
- Position sizing
- Trade signal generation
"""

from shared.models import (
    TradeSignal, MLRecommendation, RecommendationType,
    HealthCheckResponse, Position
)
from shared.logging_config import setup_logging, get_logger
from shared.firestore_client import FirestoreClient
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for shared imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Setup logging
setup_logging("strategy-engine-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Strategy Engine Service",
    description="Generates actionable trade signals from ML recommendations",
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


@app.on_event("startup")
async def startup_event():
    """Initialize clients on startup."""
    global firestore_client

    firestore_client = FirestoreClient()
    logger.info("Strategy Engine service started")


class RiskManager:
    """Risk management rules and calculations."""

    def __init__(self):
        self.logger = get_logger("RiskManager")

        # Risk management parameters
        self.max_position_size_pct = 0.10  # Max 10% of portfolio per position
        self.max_sector_allocation_pct = 0.30  # Max 30% per sector
        self.stop_loss_pct = 0.08  # 8% stop loss
        self.take_profit_pct = 0.15  # 15% take profit
        self.max_drawdown_pct = 0.20  # Max 20% drawdown before position closure
        self.min_confidence_threshold = 80.0  # Minimum ML confidence for buy signals

    async def get_portfolio_value(self) -> Decimal:
        """Get current total portfolio value."""
        try:
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("status", "==", "active")]
            )

            total_value = Decimal('0')
            for position in positions:
                market_value = position.get('market_value', 0)
                if market_value:
                    total_value += Decimal(str(market_value))

            # Add cash if tracked separately
            # For now, assume minimum portfolio value for calculations
            if total_value == 0:
                total_value = Decimal('10000')  # Default starting value

            return total_value

        except Exception as e:
            self.logger.error("Error getting portfolio value", error=str(e))
            return Decimal('10000')  # Default fallback

    async def get_position_value(self, symbol: str) -> Decimal:
        """Get current position value for a symbol."""
        try:
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("symbol", "==", symbol), ("status", "==", "active")]
            )

            if positions:
                position = positions[0]
                return Decimal(str(position.get('market_value', 0)))

            return Decimal('0')

        except Exception as e:
            self.logger.error("Error getting position value",
                              symbol=symbol, error=str(e))
            return Decimal('0')

    async def calculate_position_size(self, symbol: str, current_price: Decimal,
                                      confidence: float) -> int:
        """Calculate appropriate position size based on risk rules."""
        try:
            portfolio_value = await self.get_portfolio_value()

            # Base position size (percentage of portfolio)
            base_allocation = min(self.max_position_size_pct,
                                  confidence / 1000)  # Scale confidence

            # Adjust for confidence level
            confidence_multiplier = min(confidence / 100, 1.0)
            adjusted_allocation = base_allocation * confidence_multiplier

            # Calculate dollar amount
            position_value = portfolio_value * \
                Decimal(str(adjusted_allocation))

            # Calculate shares (minimum 1 share)
            shares = max(1, int(position_value / current_price))

            self.logger.info("Position size calculated",
                             symbol=symbol,
                             shares=shares,
                             position_value=float(position_value),
                             confidence=confidence)

            return shares

        except Exception as e:
            self.logger.error("Error calculating position size",
                              symbol=symbol, error=str(e))
            return 1  # Minimum position

    def calculate_stop_loss(self, entry_price: Decimal, signal_type: RecommendationType) -> Decimal:
        """Calculate stop loss price."""
        if signal_type == RecommendationType.BUY:
            return entry_price * (1 - Decimal(str(self.stop_loss_pct)))
        elif signal_type == RecommendationType.SELL:
            return entry_price * (1 + Decimal(str(self.stop_loss_pct)))
        else:
            return entry_price

    def calculate_take_profit(self, entry_price: Decimal, signal_type: RecommendationType) -> Decimal:
        """Calculate take profit price."""
        if signal_type == RecommendationType.BUY:
            return entry_price * (1 + Decimal(str(self.take_profit_pct)))
        elif signal_type == RecommendationType.SELL:
            return entry_price * (1 - Decimal(str(self.take_profit_pct)))
        else:
            return entry_price

    async def check_portfolio_risk_limits(self) -> bool:
        """Check if portfolio is within risk limits."""
        try:
            # For now, just check if we have too many positions
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("status", "==", "active")]
            )

            # Limit to 20 active positions max
            if len(positions) >= 20:
                self.logger.warning(
                    "Portfolio position limit reached", count=len(positions))
                return False

            return True

        except Exception as e:
            self.logger.error(
                "Error checking portfolio risk limits", error=str(e))
            return False


class StrategyEngine:
    """Main strategy engine for generating trade signals."""

    def __init__(self):
        self.risk_manager = RiskManager()
        self.logger = get_logger("StrategyEngine")

    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for a symbol."""
        try:
            # Get most recent price data
            prices = await firestore_client.query_documents(
                "di_prices_daily",
                filters=[("symbol", "==", symbol)],
                order_by="date",
                limit=1
            )

            if prices:
                return Decimal(str(prices[0]['close_price']))

            return None

        except Exception as e:
            self.logger.error("Error getting current price",
                              symbol=symbol, error=str(e))
            return None

    async def get_recent_ml_recommendations(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get recent ML recommendations."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            recommendations = await firestore_client.query_documents(
                "ml_recommendations_log",
                filters=[("created_at", ">=", cutoff_time)],
                order_by="created_at"
            )

            return recommendations

        except Exception as e:
            self.logger.error("Error getting ML recommendations", error=str(e))
            return []

    async def apply_buy_filters(self, recommendation: Dict[str, Any]) -> bool:
        """Apply filters for buy recommendations."""
        try:
            symbol = recommendation['symbol']
            confidence = recommendation['confidence_score']

            # Confidence threshold
            if confidence < self.risk_manager.min_confidence_threshold:
                self.logger.info("Buy signal filtered: low confidence",
                                 symbol=symbol, confidence=confidence)
                return False

            # Check if we already have a position
            existing_position = await self.risk_manager.get_position_value(symbol)
            if existing_position > 0:
                self.logger.info(
                    "Buy signal filtered: position already exists", symbol=symbol)
                return False

            # Check portfolio risk limits
            if not await self.risk_manager.check_portfolio_risk_limits():
                self.logger.info(
                    "Buy signal filtered: portfolio risk limits", symbol=symbol)
                return False

            return True

        except Exception as e:
            self.logger.error("Error applying buy filters", error=str(e))
            return False

    async def apply_sell_filters(self, recommendation: Dict[str, Any]) -> bool:
        """Apply filters for sell recommendations."""
        try:
            symbol = recommendation['symbol']

            # Check if we have a position to sell
            existing_position = await self.risk_manager.get_position_value(symbol)
            if existing_position <= 0:
                self.logger.info(
                    "Sell signal filtered: no position to sell", symbol=symbol)
                return False

            return True

        except Exception as e:
            self.logger.error("Error applying sell filters", error=str(e))
            return False

    async def generate_trade_signal(self, recommendation: Dict[str, Any]) -> Optional[TradeSignal]:
        """Generate a trade signal from an ML recommendation."""
        try:
            symbol = recommendation['symbol']
            rec_type = RecommendationType(recommendation['recommendation'])
            confidence = recommendation['confidence_score']

            # Get current price
            current_price = await self.get_current_price(symbol)
            if not current_price:
                self.logger.warning(
                    "Cannot generate signal: no price data", symbol=symbol)
                return None

            # Apply filters based on recommendation type
            if rec_type == RecommendationType.BUY:
                if not await self.apply_buy_filters(recommendation):
                    return None

                # Calculate position size
                quantity = await self.risk_manager.calculate_position_size(
                    symbol, current_price, confidence
                )

            elif rec_type == RecommendationType.SELL:
                if not await self.apply_sell_filters(recommendation):
                    return None

                # For sell signals, sell entire position
                positions = await firestore_client.query_documents(
                    "pf_positions_active",
                    filters=[("symbol", "==", symbol),
                             ("status", "==", "active")]
                )

                if not positions:
                    return None

                quantity = positions[0]['quantity']

            else:  # HOLD
                # No trade signal for hold recommendations
                return None

            # Calculate stop loss and take profit
            stop_loss = self.risk_manager.calculate_stop_loss(
                current_price, rec_type)
            take_profit = self.risk_manager.calculate_take_profit(
                current_price, rec_type)

            # Create trade signal
            signal = TradeSignal(
                symbol=symbol,
                signal_type=rec_type,
                quantity=abs(quantity),  # Ensure positive quantity
                price_limit=current_price,  # Use current price as limit
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reasoning=f"ML recommendation with {confidence:.1f}% confidence",
                expires_at=datetime.now() + timedelta(hours=24)  # Signal expires in 24 hours
            )

            self.logger.info("Trade signal generated",
                             symbol=symbol,
                             signal_type=rec_type.value,
                             quantity=quantity,
                             confidence=confidence)

            return signal

        except Exception as e:
            self.logger.error("Error generating trade signal", error=str(e))
            return None

    async def process_ml_recommendations(self) -> List[TradeSignal]:
        """Process recent ML recommendations and generate trade signals."""
        try:
            # Get recent recommendations
            recommendations = await self.get_recent_ml_recommendations()

            if not recommendations:
                self.logger.info("No recent ML recommendations found")
                return []

            signals = []
            processed_symbols = set()  # Avoid duplicate signals for same symbol

            # Process recommendations (most recent first)
            for rec in reversed(recommendations):
                symbol = rec['symbol']

                # Skip if we already processed this symbol
                if symbol in processed_symbols:
                    continue

                # Generate trade signal
                signal = await self.generate_trade_signal(rec)

                if signal:
                    signals.append(signal)
                    processed_symbols.add(symbol)

                    # Store signal in Firestore
                    doc_id = f"{symbol}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                    await firestore_client.upsert_document(
                        "se_trade_signals",
                        doc_id,
                        signal.dict()
                    )

            self.logger.info("ML recommendations processed",
                             recommendations_count=len(recommendations),
                             signals_generated=len(signals))

            return signals

        except Exception as e:
            self.logger.error(
                "Error processing ML recommendations", error=str(e))
            return []

    async def get_active_signals(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get active trade signals."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            signals = await firestore_client.query_documents(
                "se_trade_signals",
                filters=[
                    ("created_at", ">=", cutoff_time),
                    ("expires_at", ">", datetime.now())
                ],
                order_by="created_at"
            )

            return signals

        except Exception as e:
            self.logger.error("Error getting active signals", error=str(e))
            return []


# Global strategy engine instance
strategy_engine = StrategyEngine()


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="strategy-engine-service")


@app.post("/process-recommendations")
async def process_recommendations(background_tasks: BackgroundTasks):
    """Process recent ML recommendations and generate trade signals."""
    background_tasks.add_task(strategy_engine.process_ml_recommendations)
    return {"message": "Processing ML recommendations started"}


@app.get("/signals/active")
async def get_active_signals(hours_back: int = 24):
    """Get active trade signals."""
    signals = await strategy_engine.get_active_signals(hours_back)
    return {"signals": signals}


@app.get("/risk/status")
async def get_risk_status():
    """Get current risk management status."""
    portfolio_value = await strategy_engine.risk_manager.get_portfolio_value()
    risk_limits_ok = await strategy_engine.risk_manager.check_portfolio_risk_limits()

    return {
        "portfolio_value": float(portfolio_value),
        "risk_limits_ok": risk_limits_ok,
        "max_position_size_pct": strategy_engine.risk_manager.max_position_size_pct,
        "stop_loss_pct": strategy_engine.risk_manager.stop_loss_pct,
        "min_confidence_threshold": strategy_engine.risk_manager.min_confidence_threshold
    }


@app.post("/signals/generate/{symbol}")
async def generate_signal_for_symbol(symbol: str):
    """Generate a trade signal for a specific symbol based on latest ML recommendation."""
    try:
        # Get latest recommendation for symbol
        recommendations = await firestore_client.query_documents(
            "ml_recommendations_log",
            filters=[("symbol", "==", symbol)],
            order_by="created_at",
            limit=1
        )

        if not recommendations:
            raise HTTPException(
                status_code=404, detail=f"No ML recommendation found for {symbol}")

        signal = await strategy_engine.generate_trade_signal(recommendations[0])

        if signal:
            # Store signal in Firestore
            doc_id = f"{symbol}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            await firestore_client.upsert_document(
                "se_trade_signals",
                doc_id,
                signal.dict()
            )

            return {"signal": signal.dict()}
        else:
            return {"message": f"No trade signal generated for {symbol} (filtered out)"}

    except Exception as e:
        logger.error("Error generating signal for symbol",
                     symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
