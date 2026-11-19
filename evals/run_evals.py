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
        elif key in {"freq", "interval", "until"}:
            got = recur.split(f"{key.upper()}=")[-1].split(";")[0] if f"{key.upper()}=" in recur else ""
        elif key in {"hour", "minute"}:
            got = getattr(start, key)
        elif key == "duration_minutes":
            end = datetime.fromisoformat(body["end"]["dateTime"])
            got = int((end - start).total_seconds() // 60)
        elif key in {"summary", "title"}:
            got = body.get("summary")
        else:
            got = body.get(key)
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


def write_report(passed: int, total: int, rows: list, live: tuple | None = None) -> None:
    lines = ["# Eval report", "", f"Contract layer: **{passed}/{total} passed**", "",
             "Contract cases feed model-shaped arguments straight into the tool with a fake",
             "Google service. They prove the tool handles messy input; they say nothing",
             "about the model.", "",
             "| Case | Result | Notes |", "|---|---|---|"]
    lines += [f"| {c} | {r} | {n} |" for c, r, n in rows]
    if live:
        lpassed, ltotal, lrows, model = live
        lines += ["", f"## Live layer — `{model}`", "",
                  f"**{lpassed}/{ltotal} passed**", "",
                  "| Prompt | Result | Detail |", "|---|---|---|"]
        lines += [f"| {p} | {r} | {d} |" for p, r, d in lrows]
    Path("evals/report.md").write_text("\n".join(lines) + "\n")
    print(f"contract: {passed}/{total} passed -> evals/report.md")
    for c, r, n in rows:
        if r == "FAIL":
            print(f"  FAIL {c}: {n}")


LIVE_PROMPTS = [
    ("book lunch with priya tomorrow at 1pm for 45 minutes",
     {"title": "Lunch with Priya", "hour": 13, "duration_minutes": 45}),
    ("standup every monday at 9:15 for 15 min",
     {"hour": 9, "minute": 15, "freq": "WEEKLY"}),
    ("sync with a@x.com tomorrow at 3",
     {"attendees": "a@x.com"}),
    ("meeting in the 32nd of May at 10",
     {"must_fail": True}),
]


def live_layer() -> tuple:
    """Runs the real agent against the real model, with a fake calendar service."""
    import asyncio
    import os

    import pitu_agent
    from langchain.agents import create_agent
    from langchain.agents.middleware import ToolCallLimitMiddleware

    model = os.environ.get("MODEL", "unset")
    passed, rows = 0, []

    for prompt, expect in LIVE_PROMPTS:
        fixture = Fixture()
        original = tools.get_calendar_service
        tools.get_calendar_service = lambda token, f=fixture: f
        try:
            agent = create_agent(
                model=pitu_agent.build_model(),
                tools=tools.make_calendar_tools("fake", ZoneInfo("Asia/Singapore")),
                system_prompt=pitu_agent.SYSTEM_PROMPT,
                middleware=[
                    ToolCallLimitMiddleware(
                        tool_name="add_calendar_event", run_limit=1, exit_behavior="end"
                    )
                ],
            )
            dated = f"Today is 2026-11-19 12:00:00 +08.\nRequest: {prompt}"
            result = asyncio.run(
                agent.ainvoke({"messages": [{"role": "user", "content": dated}]},
                              config={"recursion_limit": 25})
            )
            reply = str(result["messages"][-1].content)
        except Exception as e:  # noqa: BLE001 - the failure is the result
            rows.append((prompt, "ERROR", f"{type(e).__name__}: {e}"[:80]))
            tools.get_calendar_service = original
            continue
        finally:
            tools.get_calendar_service = original

        if expect.get("must_fail"):
            ok = fixture.body is None
            detail = "did not book" if ok else "booked anyway"
        elif fixture.body is None:
            ok, detail = False, f"no tool call: {reply[:60]}"
        else:
            fails = _check(fixture.body, {k: v for k, v in expect.items() if k != "must_fail"})
            ok = not fails
            detail = "; ".join(fails) or "ok"

        try:
            from langchain_openai import ChatOpenAI  # noqa: F401
        except ImportError:
            pass
        passed += ok
        rows.append((prompt, "PASS" if ok else "FAIL", detail))

    return passed, len(rows), rows, model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    passed, total, rows = contract_layer()
    live = None
    if args.live:
        live = live_layer()
        print(f"live: {live[0]}/{live[1]} passed on {live[3]}")
        for p, r, d in live[2]:
            if r != "PASS":
                print(f"  {r} {p}: {d}")
    write_report(passed, total, rows, live)
    ok = passed == total and (live is None or live[0] == live[1])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
