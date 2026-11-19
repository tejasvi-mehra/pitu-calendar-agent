"""Contract evals: validate the tool against model-shaped arguments.

    python evals/run_evals.py          # deterministic, no network
    python evals/run_evals.py --live    # (Phase 5) real agent, costs money

The contract layer feeds each case's `args` straight into the tool with a fake
service and checks the body that would have been sent to Google. It does not
call a model, so it is reproducible and free.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools  # noqa: E402

CASES = Path(__file__).parent / "cases.jsonl"


class Fixture:
    def __init__(self):
        self.body = None

    def events(self):
        fake = self

        class Events:
            def insert(self, **kwargs):
                fake.body = kwargs["body"]
                body = kwargs["body"]

                class Req:
                    def execute(_s):
                        return {"id": "evt", "summary": body["summary"],
                                "start": body["start"], "end": body["end"]}
                return Req()
        return Events()


def _check(body: dict, expect: dict) -> list[str]:
    fails = []
    start = datetime.fromisoformat(body["start"]["dateTime"])
    recur = (body.get("recurrence") or [""])[0]
    for key, want in expect.items():
        if key == "recurrence":
            got = recur
        elif key == "attendees":
            got = ",".join(a["email"] for a in body.get("attendees", []))
        elif key == "create_meet":
            got = "conferenceData" in body
        elif key == "by_day":
            got = recur.split("BYDAY=")[-1].split(";")[0] if "BYDAY=" in recur else ""
        elif key == "count":
            got = int(recur.split("COUNT=")[-1].split(";")[0]) if "COUNT=" in recur else 0
        elif key in {"hour", "minute"}:
            got = getattr(start, key)
        elif key == "duration_minutes":
            end = datetime.fromisoformat(body["end"]["dateTime"])
            got = int((end - start).total_seconds() // 60)
        else:
            got = body.get("summary")
        if got != want:
            fails.append(f"{key}: want {want!r}, got {got!r}")
    return fails


def contract_layer() -> tuple[int, int, list]:
    tool = tools.make_calendar_tools("fake", ZoneInfo("Asia/Singapore"))[0]
    passed, rows = 0, []
    for line in CASES.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        fixture = Fixture()
        tools.get_calendar_service = lambda token, f=fixture: f  # route the tool at the fixture
        out = tool.invoke(case["args"])
        fails = _check(fixture.body, case["expect"]) if fixture.body else [out]
        ok = not fails and out.startswith("Created")
        passed += ok
        rows.append((case["id"], "PASS" if ok else "FAIL", "; ".join(fails) or out[:60]))
    return passed, len(rows), rows


def write_report(passed: int, total: int, rows: list) -> None:
    lines = ["# Eval report", "", f"Contract layer: **{passed}/{total} passed**", "",
             "| Case | Result | Notes |", "|---|---|---|"]
    lines += [f"| {c} | {r} | {n} |" for c, r, n in rows]
    Path("evals/report.md").write_text("\n".join(lines) + "\n")
    print(f"contract: {passed}/{total} passed -> evals/report.md")
    for c, r, n in rows:
        if r == "FAIL":
            print(f"  FAIL {c}: {n}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        print("live layer arrives in Phase 5")
        return
    passed, total, rows = contract_layer()
    write_report(passed, total, rows)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
