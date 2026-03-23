import logging
from datetime import datetime, timezone

from slack_bolt.async_app import AsyncApp
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from oncall.db import async_session
from oncall.models import Note, Shift, Ticket

logger = logging.getLogger(__name__)


def register_commands(app: AsyncApp) -> None:
    @app.command("/oncall")
    async def handle_oncall(ack, command, client):
        await ack()
        user_id = command["user_id"]
        channel_id = command["channel_id"]

        display_name = user_id
        try:
            info = await client.users_info(user=user_id)
            user_obj = info.get("user", {})
            profile = user_obj.get("profile", {})
            display_name = (
                profile.get("display_name_normalized")
                or profile.get("real_name_normalized")
                or user_obj.get("real_name")
                or user_obj.get("name")
                or user_id
            )
            logger.info("Resolved %s to '%s'", user_id, display_name)
        except Exception:
            logger.exception("Failed to resolve display name for %s", user_id)

        async with async_session() as session:
            result = await session.execute(
                select(Shift).where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            active = result.scalar_one_or_none()

            if active:
                return {"response_type": "ephemeral", "text": "You already have an active shift."}

            shift = Shift(
                slack_user_id=user_id,
                display_name=display_name,
                channel_id=channel_id,
                start_time=datetime.now(timezone.utc),
            )
            session.add(shift)
            await session.commit()

        return {
            "response_type": "ephemeral",
            "text": "Oncall shift started. Use `/oncall-ticket <url>` to log issues.",
        }

    @app.command("/oncall-ticket")
    async def handle_oncall_ticket(ack, command):
        await ack()
        user_id = command["user_id"]
        url = (command.get("text") or "").strip()

        if not url or not url.startswith("http"):
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/oncall-ticket <url>` -- URL must start with http.",
            }

        async with async_session() as session:
            result = await session.execute(
                select(Shift).where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                return {
                    "response_type": "ephemeral",
                    "text": "No active shift. Start one with `/oncall` first.",
                }

            ticket = Ticket(shift_id=shift.id, issue_url=url)
            session.add(ticket)
            await session.commit()

        return {"response_type": "ephemeral", "text": f"Ticket logged: {url}"}

    @app.command("/oncall-note")
    async def handle_oncall_note(ack, command):
        await ack()
        user_id = command["user_id"]
        text = (command.get("text") or "").strip()

        if not text:
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/oncall-note <what you did>`",
            }

        async with async_session() as session:
            result = await session.execute(
                select(Shift).where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                return {
                    "response_type": "ephemeral",
                    "text": "No active shift. Start one with `/oncall` first.",
                }

            note = Note(shift_id=shift.id, content=text)
            session.add(note)
            await session.commit()

        return {"response_type": "ephemeral", "text": f"Note added: {text}"}

    @app.command("/offcall")
    async def handle_offcall(ack, command, client):
        await ack()
        user_id = command["user_id"]
        channel_id = command["channel_id"]

        async with async_session() as session:
            result = await session.execute(
                select(Shift)
                .options(selectinload(Shift.tickets), selectinload(Shift.notes))
                .where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                return {
                    "response_type": "ephemeral",
                    "text": "No active shift to end.",
                }

            now = datetime.now(timezone.utc)
            shift.end_time = now
            await session.commit()

            duration = now - shift.start_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes = remainder // 60
            ticket_lines = "\n".join(f"  - {t.issue_url}" for t in shift.tickets)
            ticket_section = f"\n{ticket_lines}" if ticket_lines else "\n  (none)"
            note_lines = "\n".join(f"  - {n.content}" for n in shift.notes)
            note_section = f"\n{note_lines}" if note_lines else "\n  (none)"

            summary = (
                f"*Oncall shift ended for <@{user_id}>*\n"
                f"Duration: {hours}h {minutes}m\n"
                f"Tickets triaged ({len(shift.tickets)}):{ticket_section}\n"
                f"Notes ({len(shift.notes)}):{note_section}"
            )

            await client.chat_postMessage(channel=channel_id, text=summary)

        return {"response_type": "ephemeral", "text": "Shift ended. Summary posted to channel."}
