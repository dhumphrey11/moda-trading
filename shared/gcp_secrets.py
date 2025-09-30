"""
Google Cloud Secret Manager client for secure API key management.
"""

import os
from typing import Optional
from google.cloud import secretmanager
import structlog

logger = structlog.get_logger()


class GCPSecrets:
    """Client for Google Cloud Secret Manager."""

    def __init__(self, project_id: str = "moda-trader"):
        """Initialize Secret Manager client."""
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
        logger.info("Secret Manager client initialized", project_id=project_id)

    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """Retrieve a secret value."""
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(
                request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.info("Secret retrieved", secret_name=secret_name)
            return secret_value
        except Exception as e:
            logger.error("Failed to retrieve secret",
                         secret_name=secret_name, error=str(e))
            return None

    def create_secret(self, secret_name: str, secret_value: str) -> bool:
        """Create a new secret."""
        try:
            parent = f"projects/{self.project_id}"

            # Create the secret
            secret = {"replication": {"automatic": {}}}
            response = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": secret
                }
            )

            # Add the secret version
            payload = {"data": secret_value.encode("UTF-8")}
            self.client.add_secret_version(
                request={"parent": response.name, "payload": payload}
            )

            logger.info("Secret created", secret_name=secret_name)
            return True
        except Exception as e:
            logger.error("Failed to create secret",
                         secret_name=secret_name, error=str(e))
            return False

    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """Update an existing secret with a new version."""
        try:
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            payload = {"data": secret_value.encode("UTF-8")}

            self.client.add_secret_version(
                request={"parent": parent, "payload": payload}
            )

            logger.info("Secret updated", secret_name=secret_name)
            return True
        except Exception as e:
            logger.error("Failed to update secret",
                         secret_name=secret_name, error=str(e))
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """Delete a secret."""
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": name})
            logger.info("Secret deleted", secret_name=secret_name)
            return True
        except Exception as e:
            logger.error("Failed to delete secret",
                         secret_name=secret_name, error=str(e))
            return False


# Convenience functions for common API keys
def get_alphavantage_key() -> Optional[str]:
    """Get Alpha Vantage API key."""
    secrets = GCPSecrets()
    return secrets.get_secret("alphavantage-api-key")


def get_finnhub_key() -> Optional[str]:
    """Get Finnhub API key."""
    secrets = GCPSecrets()
    return secrets.get_secret("finnhub-api-key")


def get_polygon_key() -> Optional[str]:
    """Get Polygon.io API key."""
    secrets = GCPSecrets()
    return secrets.get_secret("polygon-api-key")


def get_tiingo_key() -> Optional[str]:
    """Get Tiingo API key."""
    secrets = GCPSecrets()
    return secrets.get_secret("tiingo-api-key")
