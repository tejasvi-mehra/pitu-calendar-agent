import json
from pathlib import Path

CASES = [
    {
        "id": "simple-lunch",
        "args": {"title": "Lunch with Priya", "date": "2026-11-20", "hour": 13, "duration_minutes": 45},
        "expect": {"summary": "Lunch with Priya", "hour": 13, "duration_minutes": 45},
    },
    {
        "id": "every-2-weeks-until",
        "args": {"title": "Meeting", "date": "2026-11-24", "hour": 10, "freq": "WEEKLY",
                 "interval": 2, "until_date": "2026-12-22"},
        "expect": {"recurrence": "RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL=20261222T235959Z"},
    },
    {
        "id": "daily-with-minute",
        "args": {"title": "Standup", "date": "2026-11-20", "hour": 9, "minute": 15,
                 "duration_minutes": 15, "freq": "DAILY", "count": 10},
        "expect": {"recurrence": "RRULE:FREQ=DAILY;COUNT=10", "hour": 9, "minute": 15},
    },
    {
        "id": "duplicate-emails",
        "args": {"title": "Sync", "date": "2026-11-20", "hour": 15, "attendees": "a@x.com, A@X.com , a@x.com"},
        "expect": {"attendees": "a@x.com", "create_meet": False},
    },
    {
        "id": "meet-link",
        "args": {"title": "Call with Bob", "date": "2026-11-20", "hour": 16,
                 "attendees": "bob@y.com", "create_meet": True},
        "expect": {"attendees": "bob@y.com", "create_meet": True},
    },
    {
        "id": "weekly-byday-8",
        "args": {"title": "Retro", "date": "2026-11-23", "hour": 17, "freq": "WEEKLY",
                 "by_day": "MO,WE,FR", "count": 8},
        "expect": {"by_day": "MO,WE,FR", "count": 8, "hour": 17},
    },
    {
        "id": "messy-date",
        "args": {"title": "Meeting", "date": "2026-11-20 13:00:00 +08", "hour": 13},
        "expect": {"hour": 13},
    },
    {
        "id": "string-bool",
        "args": {"title": "Meeting", "date": "2026-11-20", "hour": 9,
                 "attendees": "a@x.com", "create_meet": "yes"},
        "expect": {"create_meet": True},
    },
    {
        "id": "no-title",
        "args": {"title": "", "date": "2026-11-20", "hour": 9},
        "expect": {"summary": "Meeting"},
    },
    {
        "id": "count-beats-until",
        "args": {"title": "Meeting", "date": "2026-11-20", "hour": 9, "freq": "WEEKLY",
                 "count": 8, "until_date": "2026-12-22"},
        "expect": {"recurrence": "RRULE:FREQ=WEEKLY;COUNT=8"},
    },
]


def main() -> None:
    out = Path(__file__).parent / "cases.jsonl"
    out.write_text("".join(json.dumps(c) + "\n" for c in CASES))
    print(f"wrote {len(CASES)} cases to {out}")


if __name__ == "__main__":
    main()
