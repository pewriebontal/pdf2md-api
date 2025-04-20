import os
import logging
import sys
from pathlib import Path


def setup_logging():
    """Configure application logging"""
    # Define log directory in storage
    storage_dir = Path(
        os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage"
            )
        )
    )
    log_dir = storage_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)

    # Log file paths
    log_file = log_dir / "pdf2md.log"
    error_log_file = log_dir / "error.log"

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers if any
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File handler for all logs
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # File handler for error logs
    error_file_handler = logging.FileHandler(error_log_file)
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Create application logger
    app_logger = logging.getLogger("pdf2md")
    app_logger.setLevel(logging.INFO)

    return app_logger
