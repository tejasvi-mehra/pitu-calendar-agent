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
    return build("calendar", "v3", credentials=Credentials(token=token or require_token()))


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

    return [add_calendar_event]
