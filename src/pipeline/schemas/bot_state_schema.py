"""Pydantic v2 schema for bot state persistence.

Follows pipeline_status_schema.py pattern — simple Pydantic models with defaults.
Used by pause/resume (Plan 01), event scheduling (Plan 02), and custom schedules (Plan 03).
"""

from pydantic import BaseModel, Field


class PauseState(BaseModel):
    paused_until: str = ""  # ISO 8601 UTC or empty (indefinite if paused_slots non-empty)
    paused_slots: list[str] = Field(default_factory=list)  # ["morning","evening","all"]


class EventSchedule(BaseModel):
    name: str
    date: str  # ISO 8601 date
    interval_minutes: int = 30
    start_time_ist: str = ""
    end_time_ist: str = ""
    active: bool = True


class CustomSchedule(BaseModel):
    morning_ist: str = ""  # empty = use config.yaml default
    evening_ist: str = ""


class BotState(BaseModel):
    pause: PauseState = Field(default_factory=PauseState)
    events: list[EventSchedule] = Field(default_factory=list)
    custom_schedule: CustomSchedule = Field(default_factory=CustomSchedule)
