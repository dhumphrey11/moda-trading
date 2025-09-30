"""
Structured logging configuration for all services.
"""

import os
import sys
import structlog
from typing import Dict, Any


def setup_logging(service_name: str = "moda-trader", level: str = "INFO") -> None:
    """Configure structured logging for the service."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up standard library logging
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )

    # Add service context
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=os.getenv("ENVIRONMENT", "development")
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to other classes."""

    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger with class context."""
        return structlog.get_logger(self.__class__.__name__)


def log_function_call(func_name: str, **kwargs) -> Dict[str, Any]:
    """Helper to log function calls with parameters."""
    return {
        "function": func_name,
        "parameters": kwargs
    }
