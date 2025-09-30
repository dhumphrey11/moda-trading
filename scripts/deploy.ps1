# Quick Setup Script for Moda Trading

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory = $true)]
    [string]$AlphaVantageKey,
    
    [Parameter(Mandatory = $true)]
    [string]$FinnhubKey,
    
    [Parameter(Mandatory = $true)]
    [string]$PolygonKey,
    
    [Parameter(Mandatory = $true)]
    [string]$TiingoKey,
    
    [string]$Region = "us-central1"
)

Write-Host "🚀 Setting up Moda Trading on GCP..." -ForegroundColor Green

# Set project
Write-Host "Setting GCP project to $ProjectId..."
gcloud config set project $ProjectId

# Enable APIs
Write-Host "Enabling required APIs..."
$apis = @(
    "cloudbuild.googleapis.com",
    "run.googleapis.com", 
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "monitoring.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "  - Enabling $api"
    gcloud services enable $api
}

# Create Firestore database
Write-Host "Creating Firestore database..."
gcloud firestore databases create --region=$Region

# Deploy Firestore configuration
Write-Host "Deploying Firestore rules and indexes..."
gcloud firestore rules deploy infra/firestore.rules
gcloud firestore indexes deploy infra/firestore.indexes.json

# Store API keys in Secret Manager
Write-Host "Storing API keys in Secret Manager..."
$AlphaVantageKey | gcloud secrets create alphavantage-api-key --data-file=-
$FinnhubKey | gcloud secrets create finnhub-api-key --data-file=-
$PolygonKey | gcloud secrets create polygon-api-key --data-file=-
$TiingoKey | gcloud secrets create tiingo-api-key --data-file=-

# Create service account for Cloud Run services
Write-Host "Creating service account..."
gcloud iam service-accounts create moda-trader-sa --display-name="Moda Trading Service Account"

$serviceAccount = "moda-trader-sa@$ProjectId.iam.gserviceaccount.com"

# Grant necessary permissions
Write-Host "Granting permissions to service account..."
$roles = @(
    "roles/datastore.user",
    "roles/secretmanager.secretAccessor",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/monitoring.metricWriter"
)

foreach ($role in $roles) {
    gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$serviceAccount" --role=$role
}

# Build and deploy services
$services = @(
    @{name = "alphavantage-service"; path = "data-ingestion/alphavantage-service" },
    @{name = "finnhub-service"; path = "data-ingestion/finnhub-service" },
    @{name = "polygon-service"; path = "data-ingestion/polygon-service" },
    @{name = "tiingo-service"; path = "data-ingestion/tiingo-service" },
    @{name = "orchestrator-service"; path = "data-ingestion/orchestrator" },
    @{name = "ml-pipeline-service"; path = "ml-pipeline" },
    @{name = "strategy-engine-service"; path = "strategy-engine" },
    @{name = "portfolio-service"; path = "portfolio-service" }
)

Write-Host "Building and deploying services..."
foreach ($service in $services) {
    Write-Host "  - Deploying $($service.name)..." -ForegroundColor Yellow
    
    Push-Location $service.path
    
    # Build image
    gcloud builds submit --tag "gcr.io/$ProjectId/$($service.name)" .
    
    # Deploy to Cloud Run
    gcloud run deploy $service.name `
        --image "gcr.io/$ProjectId/$($service.name)" `
        --platform managed `
        --region $Region `
        --allow-unauthenticated `
        --service-account $serviceAccount `
        --set-env-vars "GCP_PROJECT_ID=$ProjectId"
    
    Pop-Location
}

# Get service URLs
Write-Host "Getting service URLs..."
$serviceUrls = @{}
foreach ($service in $services) {
    $url = gcloud run services describe $service.name --region=$Region --format="value(status.url)"
    $serviceUrls[$service.name] = $url
    Write-Host "  - $($service.name): $url"
}

# Deploy frontend
Write-Host "Deploying frontend..." -ForegroundColor Yellow
Push-Location frontend

# Install dependencies
npm install

# Update API URLs in config
$apiConfigPath = "src/services/api.ts"
$apiConfig = Get-Content $apiConfigPath -Raw

# Replace placeholder URLs with actual service URLs
$apiConfig = $apiConfig -replace "YOUR_PORTFOLIO_SERVICE_URL", $serviceUrls["portfolio-service"]
$apiConfig = $apiConfig -replace "YOUR_ML_PIPELINE_SERVICE_URL", $serviceUrls["ml-pipeline-service"]
$apiConfig = $apiConfig -replace "YOUR_STRATEGY_ENGINE_SERVICE_URL", $serviceUrls["strategy-engine-service"]
$apiConfig = $apiConfig -replace "YOUR_ORCHESTRATOR_SERVICE_URL", $serviceUrls["orchestrator-service"]

Set-Content $apiConfigPath $apiConfig

# Build frontend
npm run build

# Initialize and deploy to Firebase
firebase use $ProjectId
firebase deploy --only hosting

Pop-Location

# Set up Cloud Scheduler jobs
Write-Host "Setting up scheduled jobs..."

# Daily data collection
gcloud scheduler jobs create http daily-data-collection `
    --schedule="0 18 * * 1-5" `
    --uri="$($serviceUrls['orchestrator-service'])/orchestrate/daily" `
    --http-method=POST `
    --time-zone="America/New_York"

# Weekly model retraining
gcloud scheduler jobs create http weekly-model-training `
    --schedule="0 2 * * 0" `
    --uri="$($serviceUrls['ml-pipeline-service'])/retrain" `
    --http-method=POST `
    --time-zone="America/New_York"

# Initialize with sample data
Write-Host "Initializing with sample data..." -ForegroundColor Green

$sampleSymbols = @("AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX")

foreach ($symbol in $sampleSymbols) {
    $body = @{
        added_by = "setup"
        priority = 1
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "$($serviceUrls['portfolio-service'])/watchlist/$symbol" -Method POST -Body $body -ContentType "application/json"
}

# Trigger initial data collection
Write-Host "Triggering initial data collection..."
Invoke-RestMethod -Uri "$($serviceUrls['orchestrator-service'])/orchestrate/full" -Method POST

# Wait a moment for data to be collected
Write-Host "Waiting for data collection to complete..."
Start-Sleep -Seconds 30

# Train initial model
Write-Host "Training initial ML model..."
$trainBody = $sampleSymbols | ConvertTo-Json
Invoke-RestMethod -Uri "$($serviceUrls['ml-pipeline-service'])/train" -Method POST -Body $trainBody -ContentType "application/json"

# Display final information
Write-Host ""
Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Yellow
foreach ($service in $services) {
    Write-Host "  - $($service.name): $($serviceUrls[$service.name])"
}
Write-Host ""
Write-Host "Frontend URL: https://$ProjectId.web.app"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Access the frontend at https://$ProjectId.web.app"
Write-Host "2. Monitor services at https://console.cloud.google.com/run"
Write-Host "3. Check logs at https://console.cloud.google.com/logs"
Write-Host "4. View Firestore data at https://console.cloud.google.com/firestore"
Write-Host ""
Write-Host "The system is now collecting data and ready to generate trading recommendations!" -ForegroundColor Green