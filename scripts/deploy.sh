#!/bin/bash

# Quick Setup Script for Moda Trading on Linux/macOS

set -e

# Check if required parameters are provided
if [ $# -lt 5 ]; then
    echo "Usage: $0 <project-id> <alphavantage-key> <finnhub-key> <polygon-key> <tiingo-key> [region]"
    echo "Example: $0 moda-trader abc123 def456 ghi789 jkl012 us-central1"
    exit 1
fi

PROJECT_ID=$1
ALPHAVANTAGE_KEY=$2
FINNHUB_KEY=$3
POLYGON_KEY=$4
TIINGO_KEY=$5
REGION=${6:-us-central1}

echo "🚀 Setting up Moda Trading on GCP..."

# Set project
echo "Setting GCP project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable APIs
echo "Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    pubsub.googleapis.com \
    cloudscheduler.googleapis.com \
    monitoring.googleapis.com

# Create Firestore database
echo "Creating Firestore database..."
gcloud firestore databases create --region=$REGION

# Deploy Firestore configuration
echo "Deploying Firestore rules and indexes..."
gcloud firestore rules deploy infra/firestore.rules
gcloud firestore indexes deploy infra/firestore.indexes.json

# Store API keys in Secret Manager
echo "Storing API keys in Secret Manager..."
echo -n "$ALPHAVANTAGE_KEY" | gcloud secrets create alphavantage-api-key --data-file=-
echo -n "$FINNHUB_KEY" | gcloud secrets create finnhub-api-key --data-file=-
echo -n "$POLYGON_KEY" | gcloud secrets create polygon-api-key --data-file=-
echo -n "$TIINGO_KEY" | gcloud secrets create tiingo-api-key --data-file=-

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create moda-trader-sa --display-name="Moda Trading Service Account"

SERVICE_ACCOUNT="moda-trader-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Grant permissions
echo "Granting permissions to service account..."
for role in "roles/datastore.user" "roles/secretmanager.secretAccessor" "roles/pubsub.publisher" "roles/pubsub.subscriber" "roles/monitoring.metricWriter"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT" --role=$role
done

# Define services
declare -a services=(
    "alphavantage-service:data-ingestion/alphavantage-service"
    "finnhub-service:data-ingestion/finnhub-service"
    "polygon-service:data-ingestion/polygon-service"
    "tiingo-service:data-ingestion/tiingo-service"
    "orchestrator-service:data-ingestion/orchestrator"
    "ml-pipeline-service:ml-pipeline"
    "strategy-engine-service:strategy-engine"
    "portfolio-service:portfolio-service"
)

# Build and deploy services
echo "Building and deploying services..."
declare -A service_urls

for service_info in "${services[@]}"; do
    IFS=':' read -r service_name service_path <<< "$service_info"
    echo "  - Deploying $service_name..."
    
    cd $service_path
    
    # Build image
    gcloud builds submit --tag "gcr.io/$PROJECT_ID/$service_name" .
    
    # Deploy to Cloud Run
    gcloud run deploy $service_name \
        --image "gcr.io/$PROJECT_ID/$service_name" \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --service-account $SERVICE_ACCOUNT \
        --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID"
    
    # Get service URL
    service_url=$(gcloud run services describe $service_name --region=$REGION --format="value(status.url)")
    service_urls[$service_name]=$service_url
    echo "    URL: $service_url"
    
    cd - > /dev/null
done

# Deploy frontend
echo "Deploying frontend..."
cd frontend

# Install dependencies
npm install

# Update API URLs in config
sed -i.bak "s|YOUR_PORTFOLIO_SERVICE_URL|${service_urls[portfolio-service]}|g" src/services/api.ts
sed -i.bak "s|YOUR_ML_PIPELINE_SERVICE_URL|${service_urls[ml-pipeline-service]}|g" src/services/api.ts
sed -i.bak "s|YOUR_STRATEGY_ENGINE_SERVICE_URL|${service_urls[strategy-engine-service]}|g" src/services/api.ts
sed -i.bak "s|YOUR_ORCHESTRATOR_SERVICE_URL|${service_urls[orchestrator-service]}|g" src/services/api.ts

# Build frontend
npm run build

# Deploy to Firebase
firebase use $PROJECT_ID
firebase deploy --only hosting

cd ..

# Set up Cloud Scheduler jobs
echo "Setting up scheduled jobs..."

# Daily data collection
gcloud scheduler jobs create http daily-data-collection \
    --schedule="0 18 * * 1-5" \
    --uri="${service_urls[orchestrator-service]}/orchestrate/daily" \
    --http-method=POST \
    --time-zone="America/New_York"

# Weekly model retraining
gcloud scheduler jobs create http weekly-model-training \
    --schedule="0 2 * * 0" \
    --uri="${service_urls[ml-pipeline-service]}/retrain" \
    --http-method=POST \
    --time-zone="America/New_York"

# Initialize with sample data
echo "Initializing with sample data..."
sample_symbols=("AAPL" "MSFT" "GOOGL" "AMZN" "TSLA" "NVDA" "META" "NFLX")

for symbol in "${sample_symbols[@]}"; do
    curl -X POST "${service_urls[portfolio-service]}/watchlist/$symbol" \
        -H "Content-Type: application/json" \
        -d '{"added_by": "setup", "priority": 1}'
done

# Trigger initial data collection
echo "Triggering initial data collection..."
curl -X POST "${service_urls[orchestrator-service]}/orchestrate/full"

# Wait for data collection
echo "Waiting for data collection to complete..."
sleep 30

# Train initial model
echo "Training initial ML model..."
symbols_json=$(printf '%s\n' "${sample_symbols[@]}" | jq -R . | jq -s .)
curl -X POST "${service_urls[ml-pipeline-service]}/train" \
    -H "Content-Type: application/json" \
    -d "$symbols_json"

# Display final information
echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "Service URLs:"
for service_name in "${!service_urls[@]}"; do
    echo "  - $service_name: ${service_urls[$service_name]}"
done
echo ""
echo "Frontend URL: https://$PROJECT_ID.web.app"
echo ""
echo "Next steps:"
echo "1. Access the frontend at https://$PROJECT_ID.web.app"
echo "2. Monitor services at https://console.cloud.google.com/run"
echo "3. Check logs at https://console.cloud.google.com/logs"
echo "4. View Firestore data at https://console.cloud.google.com/firestore"
echo ""
echo "The system is now collecting data and ready to generate trading recommendations!"