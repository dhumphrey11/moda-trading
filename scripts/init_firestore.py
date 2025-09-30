"""
Firestore Database Initialization Script

This script initializes all Firestore collections with proper structure and sample data.
Run this after setting up your GCP project and Firestore database.
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add the shared directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from firestore_client import FirestoreClient
from models import (
    Stock, Company, PriceData, NewsItem, Portfolio, Position, 
    Transaction, WatchlistItem, MLModel, TradeSignal, TradingRecommendation
)


class FirestoreInitializer:
    """Initialize Firestore collections with proper structure and sample data."""
    
    def __init__(self, project_id: str):
        self.client = FirestoreClient(project_id)
        
    async def create_collections(self):
        """Create all collections with sample data."""
        print("🚀 Initializing Firestore collections...")
        
        # Initialize collections in order
        await self._init_companies()
        await self._init_stocks()
        await self._init_price_data()
        await self._init_news()
        await self._init_portfolio()
        await self._init_positions()
        await self._init_transactions()
        await self._init_watchlist()
        await self._init_ml_models()
        await self._init_trade_signals()
        await self._init_recommendations()
        
        print("✅ All Firestore collections initialized successfully!")
    
    async def _init_companies(self):
        """Initialize companies collection with sample companies."""
        print("  📊 Creating companies collection...")
        
        companies = [
            Company(
                symbol="AAPL",
                name="Apple Inc.",
                sector="Technology",
                industry="Consumer Electronics",
                market_cap=3000000000000,  # $3T
                employees=161000,
                description="Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide.",
                website="https://www.apple.com",
                headquarters="Cupertino, CA"
            ),
            Company(
                symbol="MSFT", 
                name="Microsoft Corporation",
                sector="Technology",
                industry="Software",
                market_cap=2800000000000,  # $2.8T
                employees=221000,
                description="Microsoft Corporation develops, licenses, and supports software, services, devices, and solutions worldwide.",
                website="https://www.microsoft.com",
                headquarters="Redmond, WA"
            ),
            Company(
                symbol="GOOGL",
                name="Alphabet Inc.",
                sector="Technology", 
                industry="Internet Content & Information",
                market_cap=1700000000000,  # $1.7T
                employees=182000,
                description="Alphabet Inc. provides online advertising services in the United States, Europe, the Middle East, Africa, the Asia-Pacific, Canada, and Latin America.",
                website="https://www.alphabet.com",
                headquarters="Mountain View, CA"
            ),
            Company(
                symbol="AMZN",
                name="Amazon.com Inc.",
                sector="Consumer Discretionary",
                industry="Internet Retail",
                market_cap=1500000000000,  # $1.5T
                employees=1541000,
                description="Amazon.com, Inc. engages in the retail sale of consumer products and subscriptions in North America and internationally.",
                website="https://www.amazon.com",
                headquarters="Seattle, WA"
            ),
            Company(
                symbol="TSLA",
                name="Tesla Inc.",
                sector="Consumer Discretionary",
                industry="Auto Manufacturers",
                market_cap=800000000000,  # $800B
                employees=140000,
                description="Tesla, Inc. designs, develops, manufactures, leases, and sells electric vehicles, and energy generation and storage systems.",
                website="https://www.tesla.com",
                headquarters="Austin, TX"
            )
        ]
        
        for company in companies:
            await self.client.set_document("companies", company.symbol, company.dict())
            
    async def _init_stocks(self):
        """Initialize stocks collection."""
        print("  📈 Creating stocks collection...")
        
        stocks = [
            Stock(
                symbol="AAPL",
                current_price=175.50,
                previous_close=174.20,
                day_change=1.30,
                day_change_percent=0.75,
                volume=45230000,
                market_cap=3000000000000,
                pe_ratio=28.5,
                dividend_yield=0.44,
                fifty_two_week_high=199.62,
                fifty_two_week_low=164.08,
                last_updated=datetime.utcnow()
            ),
            Stock(
                symbol="MSFT",
                current_price=378.85,
                previous_close=376.12,
                day_change=2.73,
                day_change_percent=0.73,
                volume=18450000,
                market_cap=2800000000000,
                pe_ratio=35.2,
                dividend_yield=0.68,
                fifty_two_week_high=468.35,
                fifty_two_week_low=309.45,
                last_updated=datetime.utcnow()
            ),
            Stock(
                symbol="GOOGL",
                current_price=140.25,
                previous_close=138.92,
                day_change=1.33,
                day_change_percent=0.96,
                volume=25870000,
                market_cap=1700000000000,
                pe_ratio=25.8,
                dividend_yield=0.0,
                fifty_two_week_high=153.78,
                fifty_two_week_low=121.46,
                last_updated=datetime.utcnow()
            ),
            Stock(
                symbol="AMZN",
                current_price=145.80,
                previous_close=144.35,
                day_change=1.45,
                day_change_percent=1.00,
                volume=32110000,
                market_cap=1500000000000,
                pe_ratio=52.3,
                dividend_yield=0.0,
                fifty_two_week_high=170.19,
                fifty_two_week_low=118.35,
                last_updated=datetime.utcnow()
            ),
            Stock(
                symbol="TSLA",
                current_price=248.50,
                previous_close=245.20,
                day_change=3.30,
                day_change_percent=1.35,
                volume=89340000,
                market_cap=800000000000,
                pe_ratio=65.8,
                dividend_yield=0.0,
                fifty_two_week_high=299.29,
                fifty_two_week_low=152.37,
                last_updated=datetime.utcnow()
            )
        ]
        
        for stock in stocks:
            await self.client.set_document("stocks", stock.symbol, stock.dict())
    
    async def _init_price_data(self):
        """Initialize price_data collection with historical data."""
        print("  📊 Creating price_data collection...")
        
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        base_prices = [175.50, 378.85, 140.25, 145.80, 248.50]
        
        for i, symbol in enumerate(symbols):
            # Create 30 days of historical data
            for days_back in range(30, 0, -1):
                date = datetime.utcnow() - timedelta(days=days_back)
                base_price = base_prices[i]
                
                # Simulate some price variation
                import random
                variation = random.uniform(-0.05, 0.05)  # ±5% variation
                close_price = base_price * (1 + variation)
                open_price = close_price * (1 + random.uniform(-0.02, 0.02))
                high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.03))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.03))
                volume = random.randint(20000000, 60000000)
                
                price_data = PriceData(
                    symbol=symbol,
                    date=date,
                    open=round(open_price, 2),
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    close=round(close_price, 2),
                    volume=volume,
                    adjusted_close=round(close_price, 2)
                )
                
                doc_id = f"{symbol}_{date.strftime('%Y-%m-%d')}"
                await self.client.set_document("price_data", doc_id, price_data.dict())
    
    async def _init_news(self):
        """Initialize news collection with sample news items."""
        print("  📰 Creating news collection...")
        
        news_items = [
            NewsItem(
                id="news_001",
                symbol="AAPL",
                title="Apple Reports Strong Q4 Earnings",
                summary="Apple Inc. reported better-than-expected earnings for Q4, driven by strong iPhone sales.",
                content="Apple Inc. today announced financial results for its fiscal 2024 fourth quarter...",
                source="MarketWatch",
                url="https://example.com/news/1",
                published_at=datetime.utcnow() - timedelta(hours=2),
                sentiment_score=0.8,
                relevance_score=0.95
            ),
            NewsItem(
                id="news_002", 
                symbol="TSLA",
                title="Tesla Announces New Manufacturing Plant",
                summary="Tesla plans to open a new gigafactory in the southwestern United States.",
                content="Tesla Inc. announced plans for a new manufacturing facility...",
                source="Reuters",
                url="https://example.com/news/2",
                published_at=datetime.utcnow() - timedelta(hours=5),
                sentiment_score=0.7,
                relevance_score=0.85
            ),
            NewsItem(
                id="news_003",
                symbol="MSFT",
                title="Microsoft Partners with Major Cloud Client",
                summary="Microsoft secures multi-billion dollar cloud computing contract.",
                content="Microsoft Corporation announced a significant partnership...",
                source="TechCrunch",
                url="https://example.com/news/3",
                published_at=datetime.utcnow() - timedelta(hours=8),
                sentiment_score=0.9,
                relevance_score=0.88
            )
        ]
        
        for news in news_items:
            await self.client.set_document("news", news.id, news.dict())
    
    async def _init_portfolio(self):
        """Initialize portfolio collection."""
        print("  💼 Creating portfolio collection...")
        
        portfolio = Portfolio(
            user_id="default_user",
            total_value=125000.00,
            cash_balance=25000.00,
            invested_value=100000.00,
            day_change=1250.00,
            day_change_percent=1.01,
            total_return=25000.00,
            total_return_percent=25.0,
            last_updated=datetime.utcnow()
        )
        
        await self.client.set_document("portfolio", "default_user", portfolio.dict())
    
    async def _init_positions(self):
        """Initialize positions collection with sample positions."""
        print("  📊 Creating positions collection...")
        
        positions = [
            Position(
                user_id="default_user",
                symbol="AAPL",
                quantity=100,
                average_cost=165.50,
                current_price=175.50,
                market_value=17550.00,
                unrealized_pnl=1000.00,
                unrealized_pnl_percent=6.04,
                last_updated=datetime.utcnow()
            ),
            Position(
                user_id="default_user",
                symbol="MSFT",
                quantity=50,
                average_cost=350.00,
                current_price=378.85,
                market_value=18942.50,
                unrealized_pnl=1442.50,
                unrealized_pnl_percent=8.24,
                last_updated=datetime.utcnow()
            ),
            Position(
                user_id="default_user",
                symbol="GOOGL",
                quantity=150,
                average_cost=135.00,
                current_price=140.25,
                market_value=21037.50,
                unrealized_pnl=787.50,
                unrealized_pnl_percent=3.89,
                last_updated=datetime.utcnow()
            ),
            Position(
                user_id="default_user",
                symbol="TSLA",
                quantity=75,
                average_cost=220.00,
                current_price=248.50,
                market_value=18637.50,
                unrealized_pnl=2137.50,
                unrealized_pnl_percent=12.95,
                last_updated=datetime.utcnow()
            )
        ]
        
        for position in positions:
            doc_id = f"{position.user_id}_{position.symbol}"
            await self.client.set_document("positions", doc_id, position.dict())
    
    async def _init_transactions(self):
        """Initialize transactions collection with sample transactions."""
        print("  💳 Creating transactions collection...")
        
        transactions = [
            Transaction(
                id="txn_001",
                user_id="default_user",
                symbol="AAPL",
                transaction_type="BUY",
                quantity=100,
                price=165.50,
                total_amount=16550.00,
                fees=1.00,
                timestamp=datetime.utcnow() - timedelta(days=15)
            ),
            Transaction(
                id="txn_002",
                user_id="default_user",
                symbol="MSFT",
                transaction_type="BUY",
                quantity=50,
                price=350.00,
                total_amount=17500.00,
                fees=1.00,
                timestamp=datetime.utcnow() - timedelta(days=10)
            ),
            Transaction(
                id="txn_003",
                user_id="default_user",
                symbol="GOOGL",
                transaction_type="BUY",
                quantity=150,
                price=135.00,
                total_amount=20250.00,
                fees=1.00,
                timestamp=datetime.utcnow() - timedelta(days=8)
            ),
            Transaction(
                id="txn_004",
                user_id="default_user",
                symbol="TSLA",
                transaction_type="BUY",
                quantity=75,
                price=220.00,
                total_amount=16500.00,
                fees=1.00,
                timestamp=datetime.utcnow() - timedelta(days=5)
            )
        ]
        
        for transaction in transactions:
            await self.client.set_document("transactions", transaction.id, transaction.dict())
    
    async def _init_watchlist(self):
        """Initialize watchlist collection."""
        print("  👀 Creating watchlist collection...")
        
        watchlist_items = [
            WatchlistItem(
                user_id="default_user",
                symbol="NVDA",
                added_by="user",
                priority=1,
                added_at=datetime.utcnow() - timedelta(days=3)
            ),
            WatchlistItem(
                user_id="default_user",
                symbol="META",
                added_by="user",
                priority=2,
                added_at=datetime.utcnow() - timedelta(days=2)
            ),
            WatchlistItem(
                user_id="default_user",
                symbol="NFLX",
                added_by="strategy_engine",
                priority=1,
                added_at=datetime.utcnow() - timedelta(days=1)
            )
        ]
        
        for item in watchlist_items:
            doc_id = f"{item.user_id}_{item.symbol}"
            await self.client.set_document("watchlist", doc_id, item.dict())
    
    async def _init_ml_models(self):
        """Initialize ml_models collection."""
        print("  🤖 Creating ml_models collection...")
        
        model = MLModel(
            model_id="xgboost_v1",
            model_type="classification",
            algorithm="XGBoost",
            version="1.0.0",
            features=[
                "rsi_14", "macd", "bb_position", "sma_20", "sma_50", 
                "volume_sma", "price_momentum", "volatility"
            ],
            training_symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            training_start_date=datetime.utcnow() - timedelta(days=365),
            training_end_date=datetime.utcnow() - timedelta(days=1),
            accuracy=0.68,
            precision=0.72,
            recall=0.65,
            f1_score=0.68,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        await self.client.set_document("ml_models", model.model_id, model.dict())
    
    async def _init_trade_signals(self):
        """Initialize trade_signals collection."""
        print("  📊 Creating trade_signals collection...")
        
        signals = [
            TradeSignal(
                id="signal_001",
                symbol="AAPL",
                signal="BUY",
                confidence=0.85,
                entry_price=175.50,
                stop_loss=165.00,
                take_profit=190.00,
                position_size=0.05,
                reasoning="Strong technical indicators with RSI oversold and positive momentum",
                model_id="xgboost_v1",
                generated_at=datetime.utcnow() - timedelta(minutes=30),
                expires_at=datetime.utcnow() + timedelta(hours=24),
                is_active=True
            ),
            TradeSignal(
                id="signal_002",
                symbol="TSLA",
                signal="SELL",
                confidence=0.72,
                entry_price=248.50,
                stop_loss=255.00,
                take_profit=230.00,
                position_size=0.03,
                reasoning="Overbought conditions with negative divergence in momentum indicators",
                model_id="xgboost_v1",
                generated_at=datetime.utcnow() - timedelta(minutes=15),
                expires_at=datetime.utcnow() + timedelta(hours=24),
                is_active=True
            )
        ]
        
        for signal in signals:
            await self.client.set_document("trade_signals", signal.id, signal.dict())
    
    async def _init_recommendations(self):
        """Initialize recommendations collection."""
        print("  💡 Creating recommendations collection...")
        
        recommendations = [
            TradingRecommendation(
                id="rec_001",
                user_id="default_user",
                symbol="AAPL",
                recommendation="BUY",
                confidence=0.85,
                target_price=190.00,
                stop_loss=165.00,
                reasoning="Strong fundamentals combined with positive technical setup. Q4 earnings beat expectations and guidance raised.",
                risk_score=0.3,
                expected_return=0.12,
                time_horizon="medium_term",
                model_id="xgboost_v1",
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=7),
                is_active=True
            ),
            TradingRecommendation(
                id="rec_002",
                user_id="default_user",
                symbol="MSFT",
                recommendation="HOLD",
                confidence=0.75,
                target_price=385.00,
                stop_loss=350.00,
                reasoning="Maintain current position. Cloud growth remains strong but stock is fairly valued at current levels.",
                risk_score=0.25,
                expected_return=0.08,
                time_horizon="long_term",
                model_id="xgboost_v1",
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=7),
                is_active=True
            ),
            TradingRecommendation(
                id="rec_003",
                user_id="default_user",
                symbol="TSLA",
                recommendation="SELL",
                confidence=0.68,
                target_price=230.00,
                stop_loss=255.00,
                reasoning="Technical indicators suggest short-term weakness. Consider taking profits and re-entering at lower levels.",
                risk_score=0.4,
                expected_return=-0.08,
                time_horizon="short_term",
                model_id="xgboost_v1",
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=3),
                is_active=True
            )
        ]
        
        for rec in recommendations:
            await self.client.set_document("recommendations", rec.id, rec.dict())


async def main():
    """Main function to run the initialization."""
    import asyncio
    
    # Get project ID from environment or prompt
    project_id = os.getenv('GCP_PROJECT_ID')
    if not project_id:
        project_id = input("Enter your GCP Project ID: ").strip()
        if not project_id:
            print("❌ Project ID is required!")
            return
    
    try:
        print(f"🚀 Initializing Firestore for project: {project_id}")
        initializer = FirestoreInitializer(project_id)
        await initializer.create_collections()
        print("\n🎉 Firestore initialization completed successfully!")
        print("\nCollections created:")
        print("  - companies: Company information and fundamentals")
        print("  - stocks: Current stock data and prices")
        print("  - price_data: Historical price and volume data")
        print("  - news: News articles and sentiment analysis")
        print("  - portfolio: User portfolio summaries")
        print("  - positions: Individual stock positions")
        print("  - transactions: Trade transaction history")
        print("  - watchlist: Symbols being monitored")
        print("  - ml_models: Machine learning model metadata")
        print("  - trade_signals: Generated trading signals")
        print("  - recommendations: AI-powered trading recommendations")
        
    except Exception as e:
        print(f"❌ Error initializing Firestore: {e}")
        print("Make sure you have:")
        print("  1. Set up a GCP project")
        print("  2. Enabled Firestore API")
        print("  3. Set up authentication (GOOGLE_APPLICATION_CREDENTIALS)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())