import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oncall.db import get_session
from oncall.main import app
from oncall.models import Base, Shift, Ticket


@pytest.fixture()
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
async def client(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_shifts_empty(client):
    resp = await client.get("/api/shifts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_shift_not_found(client):
    resp = await client.get(f"/api/shifts/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shift_with_tickets(client, session):
    shift = Shift(
        id=uuid.uuid4(),
        slack_user_id="U123",
        channel_id="C456",
        start_time=datetime.now(timezone.utc),
    )
    session.add(shift)
    await session.flush()

    ticket = Ticket(id=uuid.uuid4(), shift_id=shift.id, issue_url="https://github.com/org/repo/issues/1")
    session.add(ticket)
    await session.commit()

    resp = await client.get(f"/api/shifts/{shift.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slack_user_id"] == "U123"
    assert len(data["tickets"]) == 1
    assert data["tickets"][0]["issue_url"] == "https://github.com/org/repo/issues/1"


@pytest.mark.asyncio
async def test_active_shifts(client, session):
    shift = Shift(
        id=uuid.uuid4(),
        slack_user_id="U789",
        channel_id="C456",
        start_time=datetime.now(timezone.utc),
    )
    session.add(shift)
    await session.commit()

    resp = await client.get("/api/shifts/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slack_user_id"] == "U789"


@pytest.mark.asyncio
async def test_stats_empty(client):
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_shifts"] == 0
