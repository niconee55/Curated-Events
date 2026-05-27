"""Configuration loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _get_int(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    timezone: str = "America/New_York"

    database_url: str = "sqlite:///./curated_events.sqlite"

    google_credentials_file: str = ""
    google_token_file: str = "token.json"
    google_calendar_id: str = ""
    google_calendar_name: str = "Curated Events"
    ticketmaster_api_key: str = ""

    discovery_days_ahead: int = 60
    discovery_days_start_offset: int = 1

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        timezone=os.getenv("TIMEZONE", "America/New_York"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./curated_events.sqlite"),
        google_credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", ""),
        google_token_file=os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
        google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", ""),
        google_calendar_name=os.getenv("GOOGLE_CALENDAR_NAME", "Curated Events"),
        ticketmaster_api_key=os.getenv("TICKETMASTER_API_KEY", ""),
        discovery_days_ahead=_get_int(os.getenv("DISCOVERY_DAYS_AHEAD"), 60),
        discovery_days_start_offset=_get_int(os.getenv("DISCOVERY_DAYS_START_OFFSET"), 1),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
