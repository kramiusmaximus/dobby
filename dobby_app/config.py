from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    telegram_user_id: int = 0
    telegram_webhook_secret: str = ""
    telegram_poll_interval_seconds: int = 60
    telegram_context_message_count: int = Field(10, alias="TELEGRAM_CONTEXT_MESSAGE_COUNT")
    public_webhook_base_url: str = ""
    log_level: str = Field("DEBUG", alias="LOG_LEVEL")

    openai_api_key: str = ""

    obsidian_api_url: str = "http://obsidian:27123"
    obsidian_api_key: str = ""
    obsidian_verify_tls: bool = Field(False, alias="OBSIDIAN_VERIFY_TLS")
    obsidian_enabled: bool | None = Field(None, alias="OBSIDIAN_ENABLED")

    database_url: str = "sqlite:///./dobby.db"
    redis_url: str = "redis://localhost:6379/0"

    app_timezone: str = "Europe/Moscow"
    wiki_root: Path = Path("wiki")
    media_root: Path = Path("storage/media")
    automations_root: Path = Path("data/automations")

    ical_caldav_url: str = "https://caldav.icloud.com"
    ical_caldav_username: str = ""
    ical_caldav_password: str = ""
    ical_calendar_name: str = ""
    ical_reminder_calendar_name: str = ""

    planner_model: str = Field("gpt-4.1-mini", alias="PLANNER_MODEL")
    executioner_model: str = Field("gpt-4.1", alias="EXECUTOR_MODEL")
    transcription_model: str = Field("gpt-4o-mini-transcribe", alias="TRANSCRIPTION_MODEL")
    wiki_maintenance_model: str = Field("gpt-4.1", alias="WIKI_MAINTENANCE_MODEL")
    daily_briefing_model: str = Field("gpt-4.1-mini", alias="DAILY_BRIEFING_MODEL")

    @field_validator("telegram_user_id", mode="before")
    @classmethod
    def empty_user_id_is_zero(cls, value: object) -> object:
        if value == "":
            return 0
        return value

    @field_validator("obsidian_enabled", mode="before")
    @classmethod
    def empty_obsidian_enabled_is_auto(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def effective_obsidian_enabled(self) -> bool:
        if self.obsidian_enabled is not None:
            return self.obsidian_enabled
        return bool(self.obsidian_api_url and self.obsidian_api_key)


settings = Settings()
