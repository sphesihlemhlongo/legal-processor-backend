import logging
import sys
from datetime import datetime
from pathlib import Path
import os


def setup_logging():
    """Configure logging for the application"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    handlers = []

    # Detect if running on Vercel (serverless read-only FS)
    on_vercel = os.environ.get("VERCEL", None) is not None

    if not on_vercel:
        # Local/dev: enable file logging
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"legal_processor_{timestamp}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Always enable console logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for h in handlers:
        root_logger.addHandler(h)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for a specific module"""
    return logging.getLogger(name)


# Initialize logging when module is imported
setup_logging()
