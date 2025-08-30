import logging
import sys
from datetime import datetime
from pathlib import Path
import os

def setup_logging():
    """Configure logging for the application (Vercel-safe)"""

    # Use /tmp for ephemeral logging in serverless
    logs_dir = Path("/tmp/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"legal_processor_{timestamp}.log"

    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler (safe only in /tmp)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler (Vercel picks up stdout/stderr for logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if re-imported
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for a specific module"""
    return logging.getLogger(name)

# Initialize logging when module is imported
setup_logging()
