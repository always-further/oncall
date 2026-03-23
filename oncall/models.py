import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    slack_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="shift", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="shift", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_one_active_shift_per_user",
            "slack_user_id",
            unique=True,
            postgresql_where=(end_time.is_(None)),
        ),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    issue_url: Mapped[str] = mapped_column(Text, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    shift: Mapped[Shift] = relationship(back_populates="tickets")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    shift: Mapped[Shift] = relationship(back_populates="notes")
