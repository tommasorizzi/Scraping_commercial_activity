"""
Structured logging for the scraping pipeline.

Creates a logger that writes DEBUG-level messages to a daily log file
and INFO-level messages to the console.
"""

import logging
import os
from datetime import datetime
from execution.utils.config import Config


def setup_logger(name: str) -> logging.Logger:
    """Return a configured logger that writes to file + console.

    Args:
        name: Logger name (usually the script/module name).

    Returns:
        A ``logging.Logger`` instance ready to use.
    """
    Config.ensure_directories()

    logger = logging.getLogger(name)

    # Prevent duplicate handlers when called more than once
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ---- File handler (DEBUG) ----
    log_file = os.path.join(
        Config.LOGS_DIR,
        f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # ---- Console handler (INFO) ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # ---- Formatter ----
    fmt = logging.Formatter(
        "%(asctime)s | %(name)-24s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(fmt)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
