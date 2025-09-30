"""
ML Pipeline Service

Handles:
- Feature engineering from ingested data
- Model training and retraining
- Generating stock recommendations
- Model performance tracking
"""

from shared.models import (
    MLRecommendation, ModelMetadata, RecommendationType,
    DataProvider, HealthCheckResponse
)
from shared.logging_config import setup_logging, get_logger
from shared.firestore_client import FirestoreClient
import asyncio
import os
import pickle
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
import joblib

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for shared imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Setup logging
setup_logging("ml-pipeline-service")
logger = get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="ML Pipeline Service",
    description="AI/ML models for stock trading recommendations",
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
    logger.info("ML Pipeline service started")


class FeatureEngineer:
    """Feature engineering for stock data."""

    def __init__(self):
        self.logger = get_logger("FeatureEngineer")

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators from price data."""
        try:
            # Sort by date to ensure correct calculations
            df = df.sort_values('date')

            # Moving averages
            df['sma_5'] = df['close_price'].rolling(window=5).mean()
            df['sma_10'] = df['close_price'].rolling(window=10).mean()
            df['sma_20'] = df['close_price'].rolling(window=20).mean()
            df['sma_50'] = df['close_price'].rolling(window=50).mean()

            # Exponential moving averages
            df['ema_12'] = df['close_price'].ewm(span=12).mean()
            df['ema_26'] = df['close_price'].ewm(span=26).mean()

            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # RSI
            delta = df['close_price'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # Bollinger Bands
            df['bb_middle'] = df['close_price'].rolling(window=20).mean()
            bb_std = df['close_price'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            df['bb_position'] = (
                df['close_price'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

            # Volume indicators
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']

            # Price ratios
            df['price_change'] = df['close_price'].pct_change()
            df['price_change_5d'] = df['close_price'].pct_change(periods=5)
            df['price_change_10d'] = df['close_price'].pct_change(periods=10)

            # Volatility
            df['volatility'] = df['price_change'].rolling(window=20).std()

            self.logger.info("Technical indicators calculated",
                             symbol=df['symbol'].iloc[0] if len(df) > 0 else "unknown")
            return df

        except Exception as e:
            self.logger.error(
                "Error calculating technical indicators", error=str(e))
            return df

    def create_target_variable(self, df: pd.DataFrame, forward_days: int = 5,
                               threshold: float = 0.02) -> pd.DataFrame:
        """Create target variable for classification (buy/hold/sell)."""
        try:
            # Calculate future returns
            df['future_return'] = df['close_price'].shift(
                -forward_days) / df['close_price'] - 1

            # Create target variable
            conditions = [
                df['future_return'] > threshold,      # Buy signal
                df['future_return'] < -threshold,     # Sell signal
            ]
            choices = [2, 0]  # 2=Buy, 0=Sell, 1=Hold (default)
            df['target'] = np.select(conditions, choices, default=1)

            # Remove rows with NaN future returns (at the end of the dataset)
            df = df.dropna(subset=['future_return'])

            self.logger.info("Target variable created",
                             buy_signals=sum(df['target'] == 2),
                             hold_signals=sum(df['target'] == 1),
                             sell_signals=sum(df['target'] == 0))

            return df

        except Exception as e:
            self.logger.error("Error creating target variable", error=str(e))
            return df

    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Prepare feature matrix for training."""
        try:
            # Feature columns (excluding non-features)
            exclude_cols = ['symbol', 'date', 'created_at', 'updated_at', 'provider',
                            'target', 'future_return', 'open_price', 'high_price',
                            'low_price', 'close_price', 'adjusted_close']

            feature_cols = [
                col for col in df.columns if col not in exclude_cols]

            # Remove rows with any NaN values in features
            feature_df = df[feature_cols + ['target']].dropna()

            self.logger.info("Features prepared",
                             feature_count=len(feature_cols),
                             sample_count=len(feature_df))

            return feature_df, feature_cols

        except Exception as e:
            self.logger.error("Error preparing features", error=str(e))
            return pd.DataFrame(), []


class MLModel:
    """Machine learning model for stock recommendations."""

    def __init__(self, model_name: str = "xgboost_classifier"):
        self.model_name = model_name
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.feature_importance = {}
        self.logger = get_logger("MLModel")

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Train the model and return performance metrics."""
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Store feature columns
            self.feature_columns = list(X.columns)

            # Train XGBoost model
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )

            self.model.fit(X_train_scaled, y_train)

            # Make predictions
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)

            # Calculate metrics
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, average='weighted'),
                'recall': recall_score(y_test, y_pred, average='weighted'),
                'f1_score': f1_score(y_test, y_pred, average='weighted'),
                'auc_score': roc_auc_score(y_test, y_pred_proba, multi_class='ovr', average='weighted')
            }

            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = dict(zip(
                    self.feature_columns,
                    self.model.feature_importances_.tolist()
                ))

            self.logger.info("Model trained successfully", **metrics)
            return metrics

        except Exception as e:
            self.logger.error("Error training model", error=str(e))
            return {}

    def predict(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        """Make predictions for new data."""
        try:
            if self.model is None or self.scaler is None:
                raise ValueError("Model not trained yet")

            # Ensure feature columns match
            X_features = X[self.feature_columns]

            # Scale features
            X_scaled = self.scaler.transform(X_features)

            # Make predictions
            predictions = self.model.predict(X_scaled)
            probabilities = self.model.predict_proba(X_scaled)

            results = []
            for i, (pred, proba) in enumerate(zip(predictions, probabilities)):
                confidence = max(proba) * 100  # Convert to percentage

                # Map predictions to recommendation types
                rec_mapping = {0: RecommendationType.SELL,
                               1: RecommendationType.HOLD, 2: RecommendationType.BUY}
                recommendation = rec_mapping.get(pred, RecommendationType.HOLD)

                results.append({
                    'prediction': int(pred),
                    'recommendation': recommendation,
                    'confidence': confidence,
                    'probabilities': proba.tolist()
                })

            return results

        except Exception as e:
            self.logger.error("Error making predictions", error=str(e))
            return []

    def save_model(self, model_path: str):
        """Save the trained model."""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'feature_importance': self.feature_importance,
                'model_name': self.model_name
            }
            joblib.dump(model_data, model_path)
            self.logger.info("Model saved", path=model_path)
        except Exception as e:
            self.logger.error("Error saving model",
                              path=model_path, error=str(e))

    def load_model(self, model_path: str):
        """Load a trained model."""
        try:
            model_data = joblib.load(model_path)
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_columns = model_data['feature_columns']
            self.feature_importance = model_data['feature_importance']
            self.model_name = model_data['model_name']
            self.logger.info("Model loaded", path=model_path)
        except Exception as e:
            self.logger.error("Error loading model",
                              path=model_path, error=str(e))


class MLPipeline:
    """Main ML pipeline orchestrator."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.model = MLModel()
        self.logger = get_logger("MLPipeline")

    async def get_training_data(self, symbols: List[str] = None,
                                days_back: int = 730) -> pd.DataFrame:
        """Get training data from Firestore."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Get price data
            filters = [
                ("date", ">=", start_date),
                ("date", "<=", end_date)
            ]

            if symbols:
                # For multiple symbols, we'd need to query each separately in Firestore
                all_data = []
                for symbol in symbols:
                    symbol_filters = filters + [("symbol", "==", symbol)]
                    data = await firestore_client.query_documents("di_prices_daily", filters=symbol_filters)
                    all_data.extend(data)
            else:
                all_data = await firestore_client.query_documents("di_prices_daily", filters=filters)

            if not all_data:
                self.logger.warning("No training data found")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(all_data)

            # Convert string dates to datetime
            df['date'] = pd.to_datetime(df['date'])

            # Convert price columns to numeric
            price_cols = ['open_price', 'high_price',
                          'low_price', 'close_price', 'adjusted_close']
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Convert volume to numeric
            if 'volume' in df.columns:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            self.logger.info("Training data retrieved",
                             symbols_count=df['symbol'].nunique(
                             ) if 'symbol' in df.columns else 0,
                             records_count=len(df))

            return df

        except Exception as e:
            self.logger.error("Error getting training data", error=str(e))
            return pd.DataFrame()

    async def train_model(self, symbols: List[str] = None) -> Optional[str]:
        """Train a new model."""
        try:
            self.logger.info("Starting model training", symbols=symbols)

            # Get training data
            df = await self.get_training_data(symbols)

            if df.empty:
                self.logger.error("No training data available")
                return None

            # Process each symbol separately for feature engineering
            all_features = []
            for symbol in df['symbol'].unique():
                symbol_df = df[df['symbol'] == symbol].copy()

                # Calculate technical indicators
                symbol_df = self.feature_engineer.calculate_technical_indicators(
                    symbol_df)

                # Create target variable
                symbol_df = self.feature_engineer.create_target_variable(
                    symbol_df)

                all_features.append(symbol_df)

            # Combine all features
            feature_df = pd.concat(all_features, ignore_index=True)

            # Prepare features for training
            training_data, feature_cols = self.feature_engineer.prepare_features(
                feature_df)

            if training_data.empty:
                self.logger.error(
                    "No valid training data after feature engineering")
                return None

            # Split features and target
            X = training_data[feature_cols]
            y = training_data['target']

            # Train model
            metrics = self.model.train(X, y)

            if not metrics:
                self.logger.error("Model training failed")
                return None

            # Save model
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = f"models/{self.model.model_name}_{model_version}.joblib"

            # Create models directory if it doesn't exist
            os.makedirs("models", exist_ok=True)
            self.model.save_model(model_path)

            # Save model metadata to Firestore
            metadata = ModelMetadata(
                model_name=self.model.model_name,
                model_version=model_version,
                training_date=datetime.now(),
                accuracy=metrics.get('accuracy', 0.0),
                precision=metrics.get('precision', 0.0),
                recall=metrics.get('recall', 0.0),
                f1_score=metrics.get('f1_score', 0.0),
                auc_score=metrics.get('auc_score', 0.0),
                hyperparameters={
                    "n_estimators": 100,
                    "max_depth": 6,
                    "learning_rate": 0.1
                },
                feature_importance=self.model.feature_importance
            )

            await firestore_client.upsert_document(
                "ml_model_metadata",
                f"{self.model.model_name}_{model_version}",
                metadata.dict()
            )

            self.logger.info("Model training completed",
                             model_version=model_version, **metrics)
            return model_version

        except Exception as e:
            self.logger.error("Error in model training", error=str(e))
            return None

    async def generate_recommendations(self, symbols: List[str]) -> List[MLRecommendation]:
        """Generate recommendations for given symbols."""
        try:
            recommendations = []

            for symbol in symbols:
                # Get recent data for the symbol
                recent_data = await firestore_client.query_documents(
                    "di_prices_daily",
                    filters=[("symbol", "==", symbol)],
                    order_by="date",
                    limit=100
                )

                if not recent_data:
                    self.logger.warning("No recent data found", symbol=symbol)
                    continue

                # Convert to DataFrame and prepare features
                df = pd.DataFrame(recent_data)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')

                # Convert price columns to numeric
                price_cols = ['open_price', 'high_price',
                              'low_price', 'close_price', 'adjusted_close']
                for col in price_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                if 'volume' in df.columns:
                    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

                # Calculate technical indicators
                df = self.feature_engineer.calculate_technical_indicators(df)

                # Get the most recent row for prediction
                latest_data = df.iloc[-1:].copy()

                # Make prediction
                predictions = self.model.predict(
                    latest_data[self.model.feature_columns])

                if predictions:
                    pred = predictions[0]

                    # Create recommendation
                    recommendation = MLRecommendation(
                        symbol=symbol,
                        recommendation=pred['recommendation'],
                        confidence_score=pred['confidence'],
                        model_version=self.model.model_name,
                        features_used={col: float(latest_data[col].iloc[0])
                                       # Store top 10 features
                                       for col in self.model.feature_columns[:10]}
                    )

                    recommendations.append(recommendation)

                    # Store in Firestore
                    doc_id = f"{symbol}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                    await firestore_client.upsert_document(
                        "ml_recommendations_log",
                        doc_id,
                        recommendation.dict()
                    )

            self.logger.info("Recommendations generated",
                             count=len(recommendations))
            return recommendations

        except Exception as e:
            self.logger.error("Error generating recommendations", error=str(e))
            return []


# Global pipeline instance
ml_pipeline = MLPipeline()


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(service="ml-pipeline-service")


@app.post("/train")
async def train_model(background_tasks: BackgroundTasks, symbols: List[str] = None):
    """Train a new model."""
    background_tasks.add_task(ml_pipeline.train_model, symbols)
    return {"message": "Model training started"}


@app.post("/recommend")
async def generate_recommendations(symbols: List[str]):
    """Generate recommendations for symbols."""
    recommendations = await ml_pipeline.generate_recommendations(symbols)
    return {"recommendations": [rec.dict() for rec in recommendations]}


@app.get("/model/status")
async def get_model_status():
    """Get current model status."""
    return {
        "model_name": ml_pipeline.model.model_name,
        "is_trained": ml_pipeline.model.model is not None,
        "feature_count": len(ml_pipeline.model.feature_columns),
        "top_features": dict(list(ml_pipeline.model.feature_importance.items())[:10]) if ml_pipeline.model.feature_importance else {}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
