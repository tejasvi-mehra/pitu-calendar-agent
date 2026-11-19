import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.tools import tool

DEFAULT_TZ = "Asia/Singapore"


def parse_date_only(value: str) -> str:
    """Accept '2026-07-16' or messy '2026-07-16 17:00:00 +08' → '2026-07-16'."""
    s = value.strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if not m:
        raise ValueError(f"date must start with YYYY-MM-DD, got '{value}'")
    return m.group(1)


def coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def require_token() -> str:
    token = os.environ.get("GOOGLE_TOKEN", "")
    if not token:
        raise RuntimeError("GOOGLE_TOKEN not set")
    return token


def get_calendar_service(token: str | None = None):
    """Build a service from an access token. No refresh: tokens last under an hour.

    shortcut: token comes from the request or env, never from disk.
    """
    return build(
        "calendar", "v3", credentials=Credentials(token=token or require_token()), cache_discovery=False
    )


def build_rrule(
    freq: str, interval: int, count: int, until_date: str, by_day: str
) -> str | None:
    freq_n = (freq or "").strip().upper()
    if not freq_n:
        return None
    if freq_n not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
        raise ValueError(f"bad freq: {freq}")
    parts = [f"FREQ={freq_n}"]
    if int(interval) > 1:
        parts.append(f"INTERVAL={int(interval)}")
    if by_day.strip():
        parts.append(f"BYDAY={by_day.strip().upper().replace(' ', '')}")
    if int(count) > 0:
        parts.append(f"COUNT={int(count)}")
    elif until_date.strip():
        # UNTIL in UTC basic format for timed events
        y, m, d = map(int, until_date.strip()[:10].split("-"))
        parts.append(f"UNTIL={y:04d}{m:02d}{d:02d}T235959Z")
    return "RRULE:" + ";".join(parts)


def _create_event(
    service: Any,
    title: str,
    date: str,
    hour: int,
    minute: int = 0,
    duration_minutes: int = 30,
    location: str = "",
    description: str = "",
    freq: str = "",
    interval: int = 1,
    count: int = 0,
    until_date: str = "",
    by_day: str = "",
    attendees: str = "",
    create_meet: bool = False,
    tz: ZoneInfo = None,
) -> str:
    """The one implementation. Never raises: the caller reads the string."""
    tz = tz or ZoneInfo(DEFAULT_TZ)
    title = (title or "Meeting").strip() or "Meeting"
    date = parse_date_only(date)
    hour = int(hour)
    minute = int(minute)
    duration_minutes = int(duration_minutes)
    interval = int(interval)
    count = int(count)
    create_meet = coerce_bool(create_meet)
    # dedupe emails, case-insensitive
    emails = []
    seen = set()
    for e in attendees.split(","):
        e = e.strip().lower()
        if e and e not in seen:
            seen.add(e)
            emails.append(e)
    try:
        start_dt = datetime.strptime(date, "%Y-%m-%d").replace(
            hour=int(hour), minute=int(minute), second=0, tzinfo=tz
        )
        end_dt = start_dt + timedelta(minutes=int(duration_minutes))
        body: dict[str, Any] = {
            "summary": title,
            "description": description or None,
            "location": location or None,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": str(tz)},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": str(tz)},
        }
        if emails:
            body["attendees"] = [{"email": e} for e in emails]
        rrule = build_rrule(freq, interval, count, until_date, by_day)
        if rrule:
            body["recurrence"] = [rrule]
        if create_meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        created = (
            service.events()
            .insert(
                calendarId="primary",
                body=body,
                conferenceDataVersion=1 if create_meet else 0,
                sendUpdates="all" if emails else "none",
            )
            .execute()
        )
        meet = created.get("hangoutLink") or ""
        if not meet and created.get("conferenceData"):
            for ep in created["conferenceData"].get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet = ep.get("uri", "")
                    break
        parts = [
            f"Created '{created.get('summary')}'",
            f"{created['start'].get('dateTime')} → {created['end'].get('dateTime')}",
            f"id={created.get('id')}",
        ]
        if emails:
            parts.append(f"invited={emails}")
        if rrule:
            parts.append(rrule)
        if meet:
            parts.append(f"meet={meet}")
        return "; ".join(parts)
    except Exception as e:
        return f"Failed to create event: {type(e).__name__}: {e}"


def _list_events(service: Any, days: int = 7, max_results: int = 10) -> str:
    """Upcoming events in the next N days. Never raises."""
    try:
        now = datetime.now(tz=ZoneInfo(DEFAULT_TZ)).replace(microsecond=0)
        end = now + timedelta(days=int(days))
        resp = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                maxResults=int(max_results),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = resp.get("items", [])
        if not items:
            return f"No events in the next {days} days"
        lines = []
        for e in items:
            start = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date", "")
            guests = [a.get("email", "") for a in e.get("attendees", []) if not a.get("self")]
            meet = e.get("hangoutLink") or ""
            extra = []
            if guests:
                extra.append(f"guests={','.join(guests)}")
            if meet:
                extra.append("has_meet")
            suffix = f" | {' | '.join(extra)}" if extra else " | no_guests | no_meet"
            lines.append(f"{start} | {e.get('summary', '(untitled)')} | id={e.get('id')}{suffix}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list events: {type(e).__name__}: {e}"


def _delete_event(service: Any, event_id: str) -> str:
    """Delete by id. Never raises; a missing id is reported, not hidden."""
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"Deleted event id={event_id}"
    except Exception as e:
        return f"Failed to delete event: {type(e).__name__}: {e}"


def _update_event(
    service: Any,
    event_id: str,
    add_attendees: str = "",
    title: str = "",
    date: str = "",
    hour: int = -1,
    minute: int = -1,
    duration_minutes: int = -1,
    description: str = "",
    tz: ZoneInfo = None,
) -> str:
    """Patch an existing event. Only the fields given are changed. Never raises."""
    tz = tz or ZoneInfo(DEFAULT_TZ)
    try:
        current = service.events().get(calendarId="primary", eventId=event_id).execute()
        patch: dict[str, Any] = {}

        if (title or "").strip():
            patch["summary"] = title.strip()
        if (description or "").strip():
            patch["description"] = description

        if (add_attendees or "").strip():
            existing = [a.get("email", "").lower() for a in current.get("attendees", [])]
            emails = list(existing)
            for e in add_attendees.split(","):
                e = e.strip().lower()
                if e and e not in emails:
                    emails.append(e)
            patch["attendees"] = [{"email": e} for e in emails if e]

        if date.strip() or int(hour) >= 0 or int(minute) >= 0:
            start = current.get("start") or {}
            raw = date.strip() if date.strip() else (start.get("dateTime") or "")
            if not raw:
                return "Failed to update event: event has no start time to keep"
            base = datetime.fromisoformat(raw)
            new_hour = int(hour) if int(hour) >= 0 else base.hour
            new_minute = int(minute) if int(minute) >= 0 else base.minute
            delta = int(duration_minutes) if int(duration_minutes) >= 0 else int(
                (
                    datetime.fromisoformat(current["end"]["dateTime"])
                    - datetime.fromisoformat(current["start"]["dateTime"])
                ).total_seconds()
                // 60
            )
            new_start = base.replace(hour=new_hour, minute=new_minute, second=0, tzinfo=tz)
            patch["start"] = {"dateTime": new_start.isoformat(), "timeZone": str(tz)}
            patch["end"] = {
                "dateTime": (new_start + timedelta(minutes=delta)).isoformat(),
                "timeZone": str(tz),
            }

        if not patch:
            return "Nothing to update: no fields were supplied"

        updated = (
            service.events()
            .patch(
                calendarId="primary",
                eventId=event_id,
                body=patch,
                sendUpdates="all" if "attendees" in patch else "none",
            )
            .execute()
        )
        start = (updated.get("start") or {}).get("dateTime", "")
        people = [a.get("email", "") for a in updated.get("attendees", [])]
        extra = f"; invited={people}" if people else ""
        return f"Updated '{updated.get('summary')}' at {start}; id={updated.get('id')}{extra}"
    except Exception as e:
        return f"Failed to update event: {type(e).__name__}: {e}"


def make_calendar_tools(token: str, tz: ZoneInfo) -> list:
    """Bind a token and a zone to the tools. The token never becomes a parameter."""

    @tool("add_calendar_event")
    def add_calendar_event(
        title: str,
        date: str,
        hour: int,
        minute: int = 0,
        duration_minutes: int = 30,
        location: str = "",
        description: str = "",
        freq: str = "",
        interval: int = 1,
        count: int = 0,
        until_date: str = "",
        by_day: str = "",
        attendees: str = "",
        create_meet: bool = False,
    ) -> str:
        """Create a Google Calendar event with optional recurrence, invites, and Meet link.
        Args:
            title: Event title.
            date: First occurrence date as YYYY-MM-DD.
            hour: Start hour in 24h local time (2pm -> 14).
            minute: Start minute (default 0).
            duration_minutes: Length in minutes (default 30).
            location: Optional location.
            description: Optional notes.
            freq: Recurrence frequency: "" (none), DAILY, WEEKLY, MONTHLY, YEARLY.
            interval: Repeat every N units (default 1).
            count: Number of occurrences. 0 means unlimited / use until_date.
            until_date: Last date YYYY-MM-DD. Prefer count OR until_date, not both.
            by_day: Weekdays for WEEKLY, comma-separated: MO,TU,WE,TH,FR,SA,SU.
            attendees: Comma-separated guest emails. Empty = no invites.
            create_meet: If true, attach a new Google Meet link and include it in the invite.
        """
        return _create_event(
            get_calendar_service(token),
            title,
            date,
            hour,
            minute,
            duration_minutes,
            location,
            description,
            freq,
            interval,
            count,
            until_date,
            by_day,
            attendees,
            create_meet,
            tz,
        )

    @tool("list_calendar_events")
    def list_calendar_events(days: int = 7, max_results: int = 10) -> str:
        """List upcoming events from the primary calendar.
        Args:
            days: How many days ahead to look (default 7).
            max_results: Maximum events to return (default 10).
        """
        return _list_events(get_calendar_service(token), days, max_results)

    @tool("delete_calendar_event")
    def delete_calendar_event(event_id: str) -> str:
        """Delete one event. Get the id from list_calendar_events first; never guess an id.
        Args:
            event_id: The id returned by list_calendar_events.
        """
        return _delete_event(get_calendar_service(token), event_id)

    @tool("update_calendar_event")
    def update_calendar_event(
        event_id: str,
        add_attendees: str = "",
        title: str = "",
        date: str = "",
        hour: int = -1,
        minute: int = -1,
        duration_minutes: int = -1,
        description: str = "",
    ) -> str:
        """Change an existing event without touching fields you leave alone.
        Get the id from list_calendar_events first.
        Args:
            event_id: The id returned by list_calendar_events.
            add_attendees: Emails to ADD, comma-separated. Existing guests are kept.
            title: New title. Empty keeps the current one.
            date: New date YYYY-MM-DD. Empty keeps the current one.
            hour: New start hour, 24h. -1 keeps the current one.
            minute: New start minute. -1 keeps the current one.
            duration_minutes: New length. -1 keeps the current one.
            description: New description. Empty keeps the current one.
        """
        return _update_event(
            get_calendar_service(token),
            event_id,
            add_attendees,
            title,
            date,
            hour,
            minute,
            duration_minutes,
            description,
            tz,
        )

    return [add_calendar_event, list_calendar_events, update_calendar_event, delete_calendar_event]
