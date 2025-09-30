# Moda Trading - AI-Powered Stock Trading Platform

A comprehensive, scalable monorepo for an AI-powered stock trading platform built with FastAPI microservices, React frontend, and Google Cloud Platform infrastructure.

## Architecture Overview

```
/moda-trader
  /data-ingestion          # Data collection from multiple financial APIs
    /alphavantage-service  # Alpha Vantage API service
    /finnhub-service       # Finnhub API service  
    /polygon-service       # Polygon.io API service
    /tiingo-service        # Tiingo API service
    /orchestrator          # Scheduling and coordination service
  /ml-pipeline             # AI/ML models and feature engineering
  /strategy-engine         # Trading strategies and signal generation
  /portfolio-service       # Portfolio and transaction management
  /frontend               # React web application
  /infra                  # Infrastructure as code and deployment
```

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React (TypeScript)
- **Database**: Google Cloud Firestore
- **Cloud Platform**: Google Cloud Platform
- **Deployment**: Cloud Run, Firebase Hosting
- **Orchestration**: Cloud Scheduler, Pub/Sub
- **ML**: XGBoost, LightGBM, TensorFlow
- **Monitoring**: Google Cloud Monitoring

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Google Cloud SDK
- Docker

### Setup
1. Clone the repository
2. Set up GCP project: `moda-trader`
3. Configure authentication and API keys
4. Deploy services to Cloud Run
5. Deploy frontend to Firebase Hosting

### Development
Each service can be run independently for development:

```bash
# Data ingestion services
cd data-ingestion/alphavantage-service && python main.py
cd data-ingestion/finnhub-service && python main.py
cd data-ingestion/polygon-service && python main.py
cd data-ingestion/tiingo-service && python main.py
cd data-ingestion/orchestrator && python main.py

# ML Pipeline
cd ml-pipeline && python main.py

# Strategy Engine
cd strategy-engine && python main.py

# Portfolio Service
cd portfolio-service && python main.py

# Frontend
cd frontend && npm start
```

## Database Collections (Firestore)

### Data Ingestion (`di_*`)
- `di_prices_daily` - Daily price data
- `di_prices_intraday` - Intraday price data
- `di_fundamentals` - Company fundamentals
- `di_company_news` - Company-specific news
- `di_market_news` - General market news

### ML Pipeline (`ml_*`)
- `ml_recommendations_log` - All model recommendations
- `ml_models` - Trained model artifacts
- `ml_model_metadata` - Model performance metrics

### Strategy Engine (`se_*`)
- `se_trade_signals` - Generated trading signals

### Portfolio Management (`pf_*`)
- `pf_positions_active` - Current positions
- `pf_positions_history` - Historical positions
- `pf_transactions` - All trade transactions
- `pf_watchlist` - Symbols to monitor

## API Documentation

Each service exposes FastAPI endpoints with automatic OpenAPI documentation available at `/docs`.

## Deployment

Services are deployed to Google Cloud Run with automated CI/CD pipelines. See `/infra` for infrastructure configuration.

## Contributing

Please read our contributing guidelines and code of conduct before submitting pull requests.

## License

Proprietary - All rights reserved.