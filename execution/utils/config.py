"""
Configuration loader for the scraping pipeline.

Reads settings from the .env file in the project root and exposes
them as class attributes.  All paths are resolved relative to the
project root so the scripts work regardless of cwd.
"""

import os
from dotenv import load_dotenv

# Project root is two levels up from this file (execution/utils/config.py)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class Config:
    """Central configuration — populated from environment variables."""

    # ---- API Keys ----
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    PAGESPEED_API_KEY: str = os.getenv("PAGESPEED_API_KEY", "")

    # ---- Search Parameters ----
    SEARCH_SECTOR: str = os.getenv("SEARCH_SECTOR", "electricians")
    SEARCH_LOCATION: str = os.getenv("SEARCH_LOCATION", "Kungsholmen, Stockholm, Sweden")
    SEARCH_COORDINATES: str = os.getenv("SEARCH_COORDINATES", "@59.3326,18.0388,15z")

    # ---- Rate Limiting ----
    REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # ---- Quality Scoring ----
    QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "50"))

    # ---- Paths ----
    TMP_DIR: str = os.path.join(PROJECT_ROOT, ".tmp")
    OUTPUT_DIR: str = os.path.join(PROJECT_ROOT, "output")
    LOGS_DIR: str = os.path.join(PROJECT_ROOT, "logs")
    CREDENTIALS_PATH: str = os.path.join(PROJECT_ROOT, "credentials.json")
    TOKEN_PATH: str = os.path.join(PROJECT_ROOT, "token.json")

    @classmethod
    def ensure_directories(cls) -> None:
        """Create working directories if they don't exist."""
        for directory in [cls.TMP_DIR, cls.OUTPUT_DIR, cls.LOGS_DIR]:
            os.makedirs(directory, exist_ok=True)
