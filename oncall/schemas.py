import uuid
from datetime import datetime

from pydantic import BaseModel


class TicketOut(BaseModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    issue_url: str
    logged_at: datetime

    model_config = {"from_attributes": True}


class ShiftOut(BaseModel):
    id: uuid.UUID
    slack_user_id: str
    start_time: datetime
    end_time: datetime | None
    channel_id: str
    created_at: datetime
    tickets: list[TicketOut] = []

    model_config = {"from_attributes": True}


class ShiftSummary(BaseModel):
    id: uuid.UUID
    slack_user_id: str
    start_time: datetime
    end_time: datetime | None
    channel_id: str
    ticket_count: int = 0

    model_config = {"from_attributes": True}
