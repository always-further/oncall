import logging
import re
from datetime import datetime, timezone

from slack_bolt.async_app import AsyncApp
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from oncall.db import async_session
from oncall.models import Note, Shift, Ticket

logger = logging.getLogger(__name__)

_ISSUE_NUM_RE = re.compile(r"#?(\d+)")


def _extract_issue_number(url: str) -> str | None:
    m = re.search(r"/issues/(\d+)", url)
    return m.group(1) if m else None


def register_commands(app: AsyncApp) -> None:
    @app.command("/oncall")
    async def handle_oncall(ack, respond, command, client):
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
                await respond(response_type="ephemeral", text="You already have an active shift.")
                return

            shift = Shift(
                slack_user_id=user_id,
                display_name=display_name,
                channel_id=channel_id,
                start_time=datetime.now(timezone.utc),
            )
            session.add(shift)
            await session.commit()

        await respond(
            response_type="ephemeral",
            text="Oncall shift started.\n"
                 "- `/oncall-ticket <url>` to log a ticket\n"
                 "- `/oncall-note <text>` to add a note\n"
                 "- `/offcall` to end your shift",
        )

    @app.command("/oncall-ticket")
    async def handle_oncall_ticket(ack, respond, command):
        await ack()
        user_id = command["user_id"]
        text = (command.get("text") or "").strip()

        if not text:
            await respond(response_type="ephemeral", text="Usage: `/oncall-ticket <url>` or `/oncall-ticket #123` to switch back to a ticket.")
            return

        async with async_session() as session:
            result = await session.execute(
                select(Shift)
                .options(selectinload(Shift.tickets))
                .where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                await respond(response_type="ephemeral", text="No active shift. Start one with `/oncall` first.")
                return

            # Check if user is switching to an existing ticket by issue number
            num_match = _ISSUE_NUM_RE.fullmatch(text)
            if num_match:
                issue_num = num_match.group(1)
                for t in shift.tickets:
                    if t.issue_url.endswith(f"/{issue_num}"):
                        # Deactivate all, activate this one
                        for ticket in shift.tickets:
                            ticket.is_active = False
                        t.is_active = True
                        await session.commit()
                        await respond(response_type="ephemeral", text=f"Switched to #{issue_num}. Notes will attach to this ticket.")
                        return
                await respond(response_type="ephemeral", text=f"No ticket #{issue_num} found in this shift.")
                return

            if not text.startswith("http"):
                await respond(response_type="ephemeral", text="Usage: `/oncall-ticket <url>` -- URL must start with http.")
                return

            # Deactivate all existing tickets
            for t in shift.tickets:
                t.is_active = False

            ticket = Ticket(shift_id=shift.id, issue_url=text, is_active=True)
            session.add(ticket)
            await session.commit()

        issue_num = _extract_issue_number(text)
        label = f"#{issue_num}" if issue_num else text
        await respond(response_type="ephemeral", text=f"Ticket logged: {label} (now active). Use `/oncall-note` to add notes to this ticket.")

    @app.command("/oncall-note")
    async def handle_oncall_note(ack, respond, command):
        await ack()
        user_id = command["user_id"]
        text = (command.get("text") or "").strip()

        if not text:
            await respond(response_type="ephemeral", text="Usage: `/oncall-note <what you did>`")
            return

        async with async_session() as session:
            result = await session.execute(
                select(Shift)
                .options(selectinload(Shift.tickets))
                .where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                await respond(response_type="ephemeral", text="No active shift. Start one with `/oncall` first.")
                return

            # Find active ticket
            active_ticket = None
            for t in shift.tickets:
                if t.is_active:
                    active_ticket = t
                    break

            note = Note(
                shift_id=shift.id,
                ticket_id=active_ticket.id if active_ticket else None,
                content=text,
            )
            session.add(note)
            await session.commit()

        if active_ticket:
            issue_num = _extract_issue_number(active_ticket.issue_url)
            label = f"#{issue_num}" if issue_num else active_ticket.issue_url
            await respond(response_type="ephemeral", text=f"Note added to {label}: {text}")
        else:
            await respond(response_type="ephemeral", text=f"Note added to shift: {text}")

    @app.command("/offcall")
    async def handle_offcall(ack, respond, command, client):
        await ack()
        user_id = command["user_id"]
        channel_id = command["channel_id"]

        async with async_session() as session:
            result = await session.execute(
                select(Shift)
                .options(
                    selectinload(Shift.tickets).selectinload(Ticket.notes),
                    selectinload(Shift.notes),
                )
                .where(
                    Shift.slack_user_id == user_id,
                    Shift.end_time.is_(None),
                )
            )
            shift = result.scalar_one_or_none()

            if not shift:
                await respond(response_type="ephemeral", text="No active shift to end.")
                return

            now = datetime.now(timezone.utc)
            shift.end_time = now
            await session.commit()

            duration = now - shift.start_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes = remainder // 60

            # Build summary grouped by ticket
            lines = [
                f"*Oncall shift ended for <@{user_id}>*",
                f"Duration: {hours}h {minutes}m",
            ]

            # General notes (not attached to any ticket)
            general_notes = [n for n in shift.notes if n.ticket_id is None]
            if general_notes:
                lines.append("")
                lines.append("*General notes:*")
                for n in general_notes:
                    lines.append(f"  - {n.content}")

            # Tickets with their notes
            if shift.tickets:
                lines.append("")
                lines.append(f"*Tickets ({len(shift.tickets)}):*")
                for t in shift.tickets:
                    issue_num = _extract_issue_number(t.issue_url)
                    label = f"#{issue_num}" if issue_num else t.issue_url
                    lines.append(f"  *{label}* - {t.issue_url}")
                    ticket_notes = [n for n in t.notes]
                    if ticket_notes:
                        for n in ticket_notes:
                            lines.append(f"    - {n.content}")
                    else:
                        lines.append("    (no notes)")

            if not shift.tickets and not general_notes:
                lines.append("No tickets or notes logged.")

            summary = "\n".join(lines)
            await client.chat_postMessage(channel=channel_id, text=summary)

        await respond(response_type="ephemeral", text="Shift ended. Summary posted to channel.")
