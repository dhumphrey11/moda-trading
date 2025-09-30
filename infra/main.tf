# Terraform configuration for Moda Trading infrastructure

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "moda-trader"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "monitoring.googleapis.com"
  ])

  service            = each.value
  disable_on_destroy = false
}

# Firestore database
resource "google_firestore_database" "database" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# Secret Manager secrets for API keys
resource "google_secret_manager_secret" "alphavantage_key" {
  secret_id = "alphavantage-api-key"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "finnhub_key" {
  secret_id = "finnhub-api-key"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "polygon_key" {
  secret_id = "polygon-api-key"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "tiingo_key" {
  secret_id = "tiingo-api-key"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.apis]
}

# Pub/Sub topics for orchestration
resource "google_pubsub_topic" "intraday_trigger" {
  name = "intraday-data-trigger"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "daily_trigger" {
  name = "daily-data-trigger"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "weekly_trigger" {
  name = "weekly-data-trigger"

  depends_on = [google_project_service.apis]
}

# Cloud Scheduler jobs
resource "google_cloud_scheduler_job" "intraday_schedule" {
  name        = "intraday-data-collection"
  description = "Trigger intraday data collection every 15 minutes during market hours"
  schedule    = "*/15 9-16 * * 1-5"  # Every 15 minutes, 9am-4pm, Mon-Fri
  time_zone   = "America/New_York"

  pubsub_target {
    topic_name = google_pubsub_topic.intraday_trigger.id
    data       = base64encode(jsonencode({ "type" = "intraday" }))
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "daily_schedule" {
  name        = "daily-data-collection"
  description = "Trigger daily data collection after market close"
  schedule    = "0 17 * * 1-5"  # 5 PM, Mon-Fri
  time_zone   = "America/New_York"

  pubsub_target {
    topic_name = google_pubsub_topic.daily_trigger.id
    data       = base64encode(jsonencode({ "type" = "daily" }))
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "weekly_schedule" {
  name        = "weekly-fundamental-collection"
  description = "Trigger weekly fundamental data collection"
  schedule    = "0 18 * * 0"  # 6 PM on Sunday
  time_zone   = "America/New_York"

  pubsub_target {
    topic_name = google_pubsub_topic.weekly_trigger.id
    data       = base64encode(jsonencode({ "type" = "weekly" }))
  }

  depends_on = [google_project_service.apis]
}

# Cloud Run services (will be deployed via CI/CD)
# These are placeholders - actual services will be deployed with Docker images

# Output important values
output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "firestore_database" {
  value = google_firestore_database.database.name
}

output "pubsub_topics" {
  value = {
    intraday = google_pubsub_topic.intraday_trigger.name
    daily    = google_pubsub_topic.daily_trigger.name
    weekly   = google_pubsub_topic.weekly_trigger.name
  }
}