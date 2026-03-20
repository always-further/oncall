import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oncall.models import Base, Shift, Ticket
from oncall import slack_handlers


@pytest.fixture()
async def db_session(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(slack_handlers, "async_session", factory)

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
def slack_app():
    from slack_bolt.async_app import AsyncApp

    return AsyncApp(
        token="xoxb-test",
        signing_secret="test-secret",
    )


@pytest.mark.asyncio
async def test_oncall_starts_shift(db_session, slack_app):
    register = slack_handlers.register_commands
    register(slack_app)

    command = {"user_id": "U001", "channel_id": "C001", "text": ""}
    ack = AsyncMock()

    listener = None
    for l in slack_app._listeners:
        if hasattr(l, "ack_function") or (hasattr(l, "matchers") and any(
            getattr(m, "keyword", None) == "/oncall" for m in l.matchers if hasattr(m, "keyword")
        )):
            listener = l
            break

    result = await slack_app.async_dispatch(
        {"command": "/oncall", "body": command, "ack": ack}
    )

    from sqlalchemy import select

    stmt = select(Shift).where(Shift.slack_user_id == "U001")
    result = await db_session.execute(stmt)
    shift = result.scalar_one_or_none()
    assert shift is not None
    assert shift.end_time is None
