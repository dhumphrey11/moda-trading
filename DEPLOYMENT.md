# Deployment Guide for Moda Trading

This document provides step-by-step instructions for deploying the Moda Trading application to Google Cloud Platform.

## Prerequisites

1. **Google Cloud SDK** installed and configured
2. **Docker** installed
3. **Node.js 18+** and **npm** installed
4. **Python 3.9+** installed
5. **Terraform** installed (optional, for infrastructure)

## Initial Setup

### 1. Create GCP Project

```bash
# Create new project
gcloud projects create moda-trader --name="Moda Trading"

# Set as default project
gcloud config set project moda-trader

# Enable billing (required)
# Go to https://console.cloud.google.com/billing and link the project
```

### 2. Enable Required APIs

```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    pubsub.googleapis.com \
    cloudscheduler.googleapis.com \
    monitoring.googleapis.com
```

### 3. Set Up Firestore

```bash
# Create Firestore database
gcloud firestore databases create --region=us-central1

# Deploy Firestore rules and indexes
gcloud firestore rules deploy infra/firestore.rules
gcloud firestore indexes deploy infra/firestore.indexes.json
```

### 4. Configure API Keys

Store your API keys in Google Secret Manager:

```bash
# Alpha Vantage API Key
echo -n "YOUR_ALPHAVANTAGE_API_KEY" | gcloud secrets create alphavantage-api-key --data-file=-

# Finnhub API Key
echo -n "YOUR_FINNHUB_API_KEY" | gcloud secrets create finnhub-api-key --data-file=-

# Polygon.io API Key
echo -n "YOUR_POLYGON_API_KEY" | gcloud secrets create polygon-api-key --data-file=-

# Tiingo API Key
echo -n "YOUR_TIINGO_API_KEY" | gcloud secrets create tiingo-api-key --data-file=-
```

## Deployment Options

### Option 1: Automated Deployment (Recommended)

1. **Set up Cloud Build trigger:**

```bash
# Create Cloud Build trigger
gcloud builds triggers create github \
    --repo-name=moda-trading \
    --repo-owner=YOUR_GITHUB_USERNAME \
    --branch-pattern="^main$" \
    --build-config=infra/cloudbuild.yaml
```

2. **Push to main branch** to trigger deployment

### Option 2: Manual Deployment

#### Deploy Backend Services

```bash
# Build and deploy each service
cd data-ingestion/alphavantage-service
gcloud builds submit --tag gcr.io/moda-trader/alphavantage-service
gcloud run deploy alphavantage-service \
    --image gcr.io/moda-trader/alphavantage-service \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated

# Repeat for other services...
```

#### Deploy Frontend

```bash
cd frontend
npm install
npm run build

# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize Firebase project
firebase use moda-trader

# Deploy to Firebase Hosting
firebase deploy --only hosting
```

## Configuration

### Environment Variables

Update the frontend API URLs in `frontend/src/services/api.ts`:

```typescript
const API_URLS = {
  portfolio: 'https://portfolio-service-HASH-uc.a.run.app',
  mlPipeline: 'https://ml-pipeline-service-HASH-uc.a.run.app',
  // ... other service URLs
};
```

### Service URLs

After deployment, get service URLs:

```bash
gcloud run services list --platform managed
```

## Post-Deployment Setup

### 1. Initialize Watchlist

Add some initial symbols to monitor:

```bash
# Using the portfolio service API
curl -X POST "https://portfolio-service-URL/watchlist/AAPL" \
  -H "Content-Type: application/json" \
  -d '{"added_by": "admin", "priority": 1}'
```

### 2. Trigger Initial Data Collection

```bash
# Trigger full data collection
curl -X POST "https://orchestrator-service-URL/orchestrate/full"
```

### 3. Train Initial ML Model

```bash
# Train model with initial data
curl -X POST "https://ml-pipeline-service-URL/train" \
  -H "Content-Type: application/json" \
  -d '["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]'
```

## Monitoring

### Health Checks

Check service health:

```bash
# Check all services
for service in alphavantage finnhub polygon tiingo orchestrator ml-pipeline strategy-engine portfolio; do
  echo "Checking $service-service..."
  curl https://$service-service-URL/health
done
```

### Logs

View service logs:

```bash
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

### Monitoring Dashboard

1. Go to [Google Cloud Monitoring](https://console.cloud.google.com/monitoring)
2. Create dashboards for:
   - Service health and uptime
   - API usage and rate limits
   - Portfolio performance
   - ML model accuracy

## Maintenance

### Update Services

Push code changes to trigger automatic redeployment, or manually:

```bash
cd service-directory
gcloud builds submit --tag gcr.io/moda-trader/service-name
gcloud run deploy service-name --image gcr.io/moda-trader/service-name
```

### Scale Services

```bash
gcloud run services update SERVICE_NAME \
    --min-instances=1 \
    --max-instances=10 \
    --cpu=2 \
    --memory=4Gi
```

### Backup Data

Firestore automatically backs up data. For additional backups:

```bash
gcloud firestore export gs://moda-trader-backup-bucket
```

## Troubleshooting

### Common Issues

1. **API Rate Limits**: Check orchestrator logs and API call counts
2. **Service Timeouts**: Increase Cloud Run timeout and memory
3. **Firestore Permissions**: Verify service account has proper roles
4. **Secret Access**: Ensure services can access Secret Manager

### Debug Commands

```bash
# Check service logs
gcloud logs tail "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE_NAME"

# Check Firestore data
gcloud firestore collections list

# Test service endpoints
curl https://SERVICE_URL/health
```

## Security

### Service Account Roles

Ensure services have minimal required permissions:

```bash
# Grant Firestore access
gcloud projects add-iam-policy-binding moda-trader \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/datastore.user"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding moda-trader \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
```

### Network Security

- Services use HTTPS by default
- Firestore rules restrict write access
- API keys stored securely in Secret Manager

## Cost Optimization

1. **Set Cloud Run min instances to 0** for cost savings
2. **Use free tiers** of data providers when possible
3. **Monitor API usage** to stay within limits
4. **Set up budget alerts** in Google Cloud Console

## Support

For issues or questions:
1. Check the logs first
2. Review Firestore rules and indexes
3. Verify API key configurations
4. Monitor service health endpoints