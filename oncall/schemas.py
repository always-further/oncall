import uuid
from datetime import datetime

from pydantic import BaseModel


class NoteOut(BaseModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    ticket_id: uuid.UUID | None = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    issue_url: str
    is_active: bool = False
    logged_at: datetime
    notes: list[NoteOut] = []

    model_config = {"from_attributes": True}


class ShiftOut(BaseModel):
    id: uuid.UUID
    slack_user_id: str
    display_name: str | None = None
    start_time: datetime
    end_time: datetime | None
    channel_id: str
    created_at: datetime
    tickets: list[TicketOut] = []
    notes: list[NoteOut] = []

    model_config = {"from_attributes": True}


class ShiftSummary(BaseModel):
    id: uuid.UUID
    slack_user_id: str
    display_name: str | None = None
    start_time: datetime
    end_time: datetime | None
    channel_id: str
    ticket_count: int = 0

    model_config = {"from_attributes": True}
