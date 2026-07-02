from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.validators.name import NAME_MAX_LENGTH, NAME_MIN_LENGTH


class PreferredTime(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class Lead(BaseModel):
    """Заявка лида — отправляется в тело POST /v1/leads (API_CONTRACT.md, раздел 1)."""

    request_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    phone: str
    preferred_time: PreferredTime
    source: str = "telegram_bot"
    submitted_at: datetime


class CrmError(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None


class CrmErrorResponse(BaseModel):
    status: str
    error: CrmError


class CrmSuccessResponse(BaseModel):
    status: str
    lead_id: str
    request_id: UUID
    received_at: datetime
