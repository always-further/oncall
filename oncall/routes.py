import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from oncall.db import get_session
from oncall.models import Shift, Ticket
from oncall.schemas import ShiftOut, ShiftSummary

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/shifts", response_model=list[ShiftSummary])
async def list_shifts(
    user_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Shift).order_by(Shift.start_time.desc()).limit(limit).offset(offset)
    if user_id:
        stmt = stmt.where(Shift.slack_user_id == user_id)
    result = await session.execute(stmt)
    shifts = result.scalars().all()

    out = []
    for s in shifts:
        count_result = await session.execute(
            select(func.count()).where(Ticket.shift_id == s.id)
        )
        out.append(
            ShiftSummary(
                id=s.id,
                slack_user_id=s.slack_user_id,
                start_time=s.start_time,
                end_time=s.end_time,
                channel_id=s.channel_id,
                ticket_count=count_result.scalar_one(),
            )
        )
    return out


@router.get("/shifts/active", response_model=list[ShiftSummary])
async def active_shifts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Shift).where(Shift.end_time.is_(None)).order_by(Shift.start_time.desc())
    )
    shifts = result.scalars().all()

    out = []
    for s in shifts:
        count_result = await session.execute(
            select(func.count()).where(Ticket.shift_id == s.id)
        )
        out.append(
            ShiftSummary(
                id=s.id,
                slack_user_id=s.slack_user_id,
                start_time=s.start_time,
                end_time=s.end_time,
                channel_id=s.channel_id,
                ticket_count=count_result.scalar_one(),
            )
        )
    return out


@router.get("/shifts/{shift_id}", response_model=ShiftOut)
async def get_shift(
    shift_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Shift).options(selectinload(Shift.tickets)).where(Shift.id == shift_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


@router.get("/stats")
async def shift_stats(
    user_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Shift).where(Shift.end_time.is_not(None))
    if user_id:
        stmt = stmt.where(Shift.slack_user_id == user_id)
    result = await session.execute(stmt)
    shifts = result.scalars().all()

    if not shifts:
        return {
            "total_shifts": 0,
            "total_hours": 0,
            "avg_hours": 0,
            "users": [],
        }

    user_map: dict[str, list[float]] = {}
    for s in shifts:
        duration_hours = (s.end_time - s.start_time).total_seconds() / 3600
        user_map.setdefault(s.slack_user_id, []).append(duration_hours)

    total_hours = sum(h for hrs in user_map.values() for h in hrs)
    total_shifts = sum(len(hrs) for hrs in user_map.values())

    users = []
    for uid, hrs in sorted(user_map.items()):
        users.append({
            "slack_user_id": uid,
            "shifts": len(hrs),
            "total_hours": round(sum(hrs), 2),
            "avg_hours": round(sum(hrs) / len(hrs), 2),
        })

    return {
        "total_shifts": total_shifts,
        "total_hours": round(total_hours, 2),
        "avg_hours": round(total_hours / total_shifts, 2),
        "users": users,
    }
