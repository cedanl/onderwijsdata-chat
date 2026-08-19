"""
Structured logging configuration for production deployment.
Provides JSON logging for Kubernetes log aggregation.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Outputs logs as JSON for easy parsing in log aggregation systems (ELK, Grafana Loki, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields if provided
        if hasattr(record, "extra_fields"):
            log_obj.update(record.extra_fields)

        return json.dumps(log_obj, default=str)


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatter (for production) or standard format (for development)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.upper())

    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from verbose libraries
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class StructuredLogger:
    """Helper for adding structured fields to log records."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def info(self, message: str, **extra_fields) -> None:
        record = logging.LogRecord(
            self.logger.name, logging.INFO, "", 0, message, (), None
        )
        record.extra_fields = extra_fields
        self.logger.handle(record)

    def warning(self, message: str, **extra_fields) -> None:
        record = logging.LogRecord(
            self.logger.name, logging.WARNING, "", 0, message, (), None
        )
        record.extra_fields = extra_fields
        self.logger.handle(record)

    def error(self, message: str, **extra_fields) -> None:
        record = logging.LogRecord(
            self.logger.name, logging.ERROR, "", 0, message, (), None
        )
        record.extra_fields = extra_fields
        self.logger.handle(record)
