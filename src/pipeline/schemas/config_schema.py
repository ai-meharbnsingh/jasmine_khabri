"""Pydantic v2 schema models for application configuration (config.yaml)."""

from pydantic import BaseModel, Field


class ScheduleConfig(BaseModel):
    # HH:MM in IST — MUST be quoted in YAML to prevent sexagesimal parsing
    morning_ist: str = "07:00"
    evening_ist: str = "16:00"  # HH:MM in IST


class TelegramConfig(BaseModel):
    bot_token: str = ""  # Set via env var at runtime, empty default
    chat_ids: list[str] = Field(default_factory=list)
    breaking_news_enabled: bool = True


class EmailConfig(BaseModel):
    enabled: bool = True
    recipients: list[str] = Field(default_factory=list)


class DeliveryConfig(BaseModel):
    max_stories: int = Field(default=15, ge=1, le=50)


class RssFeedConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True


class AppConfig(BaseModel):
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    rss_feeds: list[RssFeedConfig] = Field(default_factory=list)
