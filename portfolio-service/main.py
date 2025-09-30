"""
Portfolio Service

Manages:
- Active and historical positions
- Trade execution and transaction recording
- Portfolio performance tracking
- Watchlist management
"""

from shared.models import (
    Position, Transaction, WatchlistItem, TradeSignal,
    TransactionType, PositionStatus, HealthCheckResponse
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
setup_logging("portfolio-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Portfolio Service",
    description="Portfolio and transaction management service",
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
    logger.info("Portfolio service started")


class PortfolioManager:
    """Main portfolio management class."""

    def __init__(self):
        self.logger = get_logger("PortfolioManager")

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

    async def execute_trade(self, signal: Dict[str, Any]) -> Optional[str]:
        """Execute a trade based on a trade signal."""
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            quantity = signal['quantity']

            # Get current price
            current_price = await self.get_current_price(symbol)
            if not current_price:
                self.logger.error(
                    "Cannot execute trade: no price data", symbol=symbol)
                return None

            # Use limit price if available, otherwise current price
            execution_price = Decimal(
                str(signal.get('price_limit', current_price)))

            # Create transaction
            transaction_type = TransactionType.BUY if signal_type == "buy" else TransactionType.SELL
            total_amount = execution_price * quantity

            # Simple fee calculation (0.1% of trade value)
            fees = total_amount * Decimal('0.001')

            transaction = Transaction(
                symbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                price=execution_price,
                total_amount=total_amount,
                fees=fees,
                executed_at=datetime.now()
            )

            # Store transaction
            transaction_id = f"{symbol}_{transaction_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await firestore_client.upsert_document(
                "pf_transactions",
                transaction_id,
                transaction.dict()
            )

            # Update positions
            await self.update_positions(transaction)

            self.logger.info("Trade executed",
                             symbol=symbol,
                             type=transaction_type.value,
                             quantity=quantity,
                             price=float(execution_price),
                             transaction_id=transaction_id)

            return transaction_id

        except Exception as e:
            self.logger.error("Error executing trade", error=str(e))
            return None

    async def update_positions(self, transaction: Transaction):
        """Update positions based on a transaction."""
        try:
            symbol = transaction.symbol

            # Get existing position
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("symbol", "==", symbol), ("status", "==", "active")]
            )

            if transaction.transaction_type == TransactionType.BUY:
                if positions:
                    # Update existing position
                    position_data = positions[0]
                    existing_quantity = position_data['quantity']
                    existing_cost = Decimal(str(position_data['average_cost']))

                    # Calculate new average cost
                    total_cost = (existing_quantity * existing_cost) + \
                        (transaction.quantity * transaction.price)
                    new_quantity = existing_quantity + transaction.quantity
                    new_average_cost = total_cost / new_quantity

                    # Update position
                    position_data['quantity'] = new_quantity
                    position_data['average_cost'] = float(new_average_cost)
                    position_data['updated_at'] = datetime.now()

                    await firestore_client.update_document(
                        "pf_positions_active",
                        position_data['id'],
                        position_data
                    )
                else:
                    # Create new position
                    position = Position(
                        symbol=symbol,
                        quantity=transaction.quantity,
                        average_cost=transaction.price,
                        opened_at=transaction.executed_at,
                        status=PositionStatus.ACTIVE
                    )

                    position_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    await firestore_client.upsert_document(
                        "pf_positions_active",
                        position_id,
                        position.dict()
                    )

            elif transaction.transaction_type == TransactionType.SELL:
                if positions:
                    position_data = positions[0]
                    existing_quantity = position_data['quantity']

                    if transaction.quantity >= existing_quantity:
                        # Close entire position
                        position_data['status'] = PositionStatus.CLOSED.value
                        position_data['closed_at'] = transaction.executed_at
                        position_data['quantity'] = 0

                        # Move to historical positions
                        await firestore_client.upsert_document(
                            "pf_positions_history",
                            position_data['id'],
                            position_data
                        )

                        # Remove from active positions
                        await firestore_client.delete_document(
                            "pf_positions_active",
                            position_data['id']
                        )
                    else:
                        # Partial sell
                        position_data['quantity'] = existing_quantity - \
                            transaction.quantity
                        position_data['updated_at'] = datetime.now()

                        await firestore_client.update_document(
                            "pf_positions_active",
                            position_data['id'],
                            position_data
                        )

            self.logger.info("Position updated", symbol=symbol,
                             transaction_type=transaction.transaction_type.value)

        except Exception as e:
            self.logger.error("Error updating positions",
                              symbol=transaction.symbol, error=str(e))

    async def update_position_values(self):
        """Update current market values for all active positions."""
        try:
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("status", "==", "active")]
            )

            for position in positions:
                symbol = position['symbol']
                quantity = position['quantity']

                # Get current price
                current_price = await self.get_current_price(symbol)
                if current_price:
                    market_value = current_price * quantity
                    average_cost = Decimal(str(position['average_cost']))
                    unrealized_pnl = (current_price - average_cost) * quantity

                    # Update position with current values
                    position['current_price'] = float(current_price)
                    position['market_value'] = float(market_value)
                    position['unrealized_pnl'] = float(unrealized_pnl)
                    position['updated_at'] = datetime.now()

                    await firestore_client.update_document(
                        "pf_positions_active",
                        position['id'],
                        position
                    )

            self.logger.info("Position values updated", count=len(positions))

        except Exception as e:
            self.logger.error("Error updating position values", error=str(e))

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary statistics."""
        try:
            # Get active positions
            positions = await firestore_client.query_documents(
                "pf_positions_active",
                filters=[("status", "==", "active")]
            )

            # Calculate totals
            total_market_value = Decimal('0')
            total_cost_basis = Decimal('0')
            total_unrealized_pnl = Decimal('0')

            for position in positions:
                if position.get('market_value'):
                    total_market_value += Decimal(
                        str(position['market_value']))
                if position.get('average_cost') and position.get('quantity'):
                    total_cost_basis += Decimal(
                        str(position['average_cost'])) * position['quantity']
                if position.get('unrealized_pnl'):
                    total_unrealized_pnl += Decimal(
                        str(position['unrealized_pnl']))

            # Get recent transactions
            cutoff_date = datetime.now() - timedelta(days=30)
            recent_transactions = await firestore_client.query_documents(
                "pf_transactions",
                filters=[("executed_at", ">=", cutoff_date)],
                order_by="executed_at",
                limit=100
            )

            return {
                "active_positions_count": len(positions),
                "total_market_value": float(total_market_value),
                "total_cost_basis": float(total_cost_basis),
                "total_unrealized_pnl": float(total_unrealized_pnl),
                "unrealized_return_pct": float((total_unrealized_pnl / total_cost_basis * 100)) if total_cost_basis > 0 else 0,
                "recent_transactions_count": len(recent_transactions),
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error("Error getting portfolio summary", error=str(e))
            return {}

    async def process_trade_signals(self):
        """Process pending trade signals."""
        try:
            # Get recent trade signals that haven't expired
            current_time = datetime.now()
            signals = await firestore_client.query_documents(
                "se_trade_signals",
                filters=[
                    ("expires_at", ">", current_time),
                    ("created_at", ">=", current_time - timedelta(hours=24))
                ]
            )

            executed_count = 0
            for signal in signals:
                # Check if this signal has already been processed
                # (In a real system, you'd want to track processed signals)
                transaction_id = await self.execute_trade(signal)
                if transaction_id:
                    executed_count += 1

            self.logger.info("Trade signals processed",
                             signals_found=len(signals),
                             executed=executed_count)

        except Exception as e:
            self.logger.error("Error processing trade signals", error=str(e))


class WatchlistManager:
    """Watchlist management."""

    def __init__(self):
        self.logger = get_logger("WatchlistManager")

    async def add_to_watchlist(self, symbol: str, added_by: str, notes: str = None, priority: int = 1) -> bool:
        """Add a symbol to the watchlist."""
        try:
            # Check if symbol is already in watchlist
            existing = await firestore_client.query_documents(
                "pf_watchlist",
                filters=[("symbol", "==", symbol)]
            )

            if existing:
                self.logger.info("Symbol already in watchlist", symbol=symbol)
                return True

            watchlist_item = WatchlistItem(
                symbol=symbol,
                added_by=added_by,
                notes=notes,
                priority=priority
            )

            await firestore_client.upsert_document(
                "pf_watchlist",
                f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                watchlist_item.dict()
            )

            self.logger.info("Symbol added to watchlist",
                             symbol=symbol, added_by=added_by)
            return True

        except Exception as e:
            self.logger.error("Error adding to watchlist",
                              symbol=symbol, error=str(e))
            return False

    async def remove_from_watchlist(self, symbol: str) -> bool:
        """Remove a symbol from the watchlist."""
        try:
            watchlist_items = await firestore_client.query_documents(
                "pf_watchlist",
                filters=[("symbol", "==", symbol)]
            )

            for item in watchlist_items:
                await firestore_client.delete_document("pf_watchlist", item['id'])

            self.logger.info("Symbol removed from watchlist", symbol=symbol)
            return True

        except Exception as e:
            self.logger.error("Error removing from watchlist",
                              symbol=symbol, error=str(e))
            return False

    async def get_watchlist(self) -> List[Dict[str, Any]]:
        """Get current watchlist."""
        try:
            watchlist = await firestore_client.query_documents(
                "pf_watchlist",
                order_by="priority"
            )
            return watchlist

        except Exception as e:
            self.logger.error("Error getting watchlist", error=str(e))
            return []


# Global managers
portfolio_manager = PortfolioManager()
watchlist_manager = WatchlistManager()


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="portfolio-service")


@app.get("/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary."""
    summary = await portfolio_manager.get_portfolio_summary()
    return summary


@app.get("/positions/active")
async def get_active_positions():
    """Get all active positions."""
    positions = await firestore_client.query_documents(
        "pf_positions_active",
        filters=[("status", "==", "active")]
    )
    return {"positions": positions}


@app.get("/positions/history")
async def get_position_history(limit: int = 50):
    """Get historical positions."""
    positions = await firestore_client.query_documents(
        "pf_positions_history",
        order_by="closed_at",
        limit=limit
    )
    return {"positions": positions}


@app.get("/transactions")
async def get_transactions(limit: int = 100):
    """Get recent transactions."""
    transactions = await firestore_client.query_documents(
        "pf_transactions",
        order_by="executed_at",
        limit=limit
    )
    return {"transactions": transactions}


@app.post("/positions/update-values")
async def update_position_values(background_tasks: BackgroundTasks):
    """Update current market values for all positions."""
    background_tasks.add_task(portfolio_manager.update_position_values)
    return {"message": "Position value update started"}


@app.post("/trades/process-signals")
async def process_trade_signals(background_tasks: BackgroundTasks):
    """Process pending trade signals."""
    background_tasks.add_task(portfolio_manager.process_trade_signals)
    return {"message": "Trade signal processing started"}


@app.post("/trades/execute")
async def execute_trade_manual(trade_data: Dict[str, Any]):
    """Manually execute a trade."""
    transaction_id = await portfolio_manager.execute_trade(trade_data)
    if transaction_id:
        return {"message": "Trade executed", "transaction_id": transaction_id}
    else:
        raise HTTPException(status_code=400, detail="Failed to execute trade")


# Watchlist endpoints
@app.get("/watchlist")
async def get_watchlist():
    """Get current watchlist."""
    watchlist = await watchlist_manager.get_watchlist()
    return {"watchlist": watchlist}


@app.post("/watchlist/{symbol}")
async def add_to_watchlist(symbol: str, added_by: str = "system", notes: str = None, priority: int = 1):
    """Add symbol to watchlist."""
    success = await watchlist_manager.add_to_watchlist(symbol, added_by, notes, priority)
    if success:
        return {"message": f"Symbol {symbol} added to watchlist"}
    else:
        raise HTTPException(
            status_code=400, detail="Failed to add symbol to watchlist")


@app.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Remove symbol from watchlist."""
    success = await watchlist_manager.remove_from_watchlist(symbol)
    if success:
        return {"message": f"Symbol {symbol} removed from watchlist"}
    else:
        raise HTTPException(
            status_code=400, detail="Failed to remove symbol from watchlist")


# Performance endpoints
@app.get("/performance/daily")
async def get_daily_performance(days_back: int = 30):
    """Get daily portfolio performance."""
    # This would calculate daily portfolio values and returns
    # For now, return placeholder data
    return {"message": "Daily performance calculation not yet implemented"}


@app.get("/performance/holdings")
async def get_holdings_performance():
    """Get performance breakdown by holdings."""
    try:
        positions = await firestore_client.query_documents(
            "pf_positions_active",
            filters=[("status", "==", "active")]
        )

        performance_data = []
        for position in positions:
            if position.get('unrealized_pnl') is not None and position.get('average_cost'):
                cost_basis = position['average_cost'] * position['quantity']
                return_pct = (position['unrealized_pnl'] /
                              cost_basis * 100) if cost_basis > 0 else 0

                performance_data.append({
                    "symbol": position['symbol'],
                    "quantity": position['quantity'],
                    "average_cost": position['average_cost'],
                    "current_price": position.get('current_price'),
                    "market_value": position.get('market_value'),
                    "unrealized_pnl": position['unrealized_pnl'],
                    "return_pct": return_pct
                })

        return {"holdings_performance": performance_data}

    except Exception as e:
        logger.error("Error getting holdings performance", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get holdings performance")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
