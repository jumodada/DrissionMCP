"""Ten-cycle cross-origin challenge-surface capability benchmark for 0.8.7."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from time import monotonic
from typing import Any

from drissionpage_mcp import __version__
from drissionpage_mcp.compat import DRISSIONPAGE_VERSION
from drissionpage_mcp.server import DrissionPageMCPServer
from tests.evals.task_completion_benchmark import BenchmarkClient, _runtime_evidence
from tests.fixtures.http_fixture import local_http_fixture

SCENARIOS = (
    "normal",
    "hidden",
    "below_viewport",
    "delayed_mount",
    "transformed_3d",
)


class ChallengeBenchmarkFailure(AssertionError):
    """One challenge-surface scenario missed its observable contract."""


async def run_benchmark(iterations: int = 10) -> dict[str, Any]:
    """Run each generic challenge surface and return bounded JSON evidence."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    started_at = datetime.now(timezone.utc)
    runs: list[dict[str, Any]] = []
    runtimes: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        server = DrissionPageMCPServer()
        try:
            with local_http_fixture() as base_url:
                for scenario in SCENARIOS:
                    client = BenchmarkClient(server)
                    started = monotonic()
                    try:
                        evidence = await _run_scenario(client, base_url, scenario)
                        success = True
                        error = ""
                        failure_category = ""
                    except Exception as exc:
                        evidence = {}
                        success = False
                        error = f"{type(exc).__name__}: {exc}"[:500]
                        failure_category = _failure_category(error)
                    runs.append(
                        {
                            "scenario": scenario,
                            "iteration": iteration,
                            "success": success,
                            "duration_ms": round((monotonic() - started) * 1000),
                            "tool_calls": list(client.calls),
                            "tool_call_count": len(client.calls),
                            "first_geometry_error_px": evidence.get(
                                "first_geometry_error_px"
                            ),
                            "coordinate_actionability": evidence.get(
                                "coordinate_actionability", ""
                            ),
                            "postcondition": evidence.get("postcondition", ""),
                            "screenshot_bytes": evidence.get("screenshot_bytes", 0),
                            "error": error,
                            "failure_category": failure_category,
                        }
                    )
            runtimes.append(_runtime_evidence(server, iteration))
        finally:
            await server.cleanup()

    summary = _summarize(runs, iterations)
    summary["browser_evidence_complete"] = bool(runtimes) and all(
        item.get("browser_product") and item.get("browser_revision")
        for item in runtimes
    )
    summary["passed"] = bool(summary["passed"]) and bool(
        summary["browser_evidence_complete"]
    )
    return {
        "schema_version": "1",
        "release": __version__,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "iterations": iterations,
        "required_successes_per_scenario": ceil(iterations * 0.9),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "drissionpage": DRISSIONPAGE_VERSION,
            "runtimes": runtimes,
        },
        "summary": summary,
        "runs": runs,
    }


async def _run_scenario(
    client: BenchmarkClient, base_url: str, scenario: str
) -> dict[str, Any]:
    await client.call("page_navigate", {"url": base_url + "/challenge-surfaces"})
    await client.call("page_resize", {"width": 800, "height": 600})
    await client.call(
        "wait_for_element", {"selector": "#delayed-widget", "timeout": 3}
    )
    frames = await client.call("frame_list", {"limit": 10})
    by_id = {item["id"]: item for item in frames["data"]["frames"]}
    if scenario == "hidden":
        actionability = _actionability(by_id, "hidden-widget")
        _require(actionability == "hidden", "hidden frame was not classified")
        screenshot = await client.call("page_screenshot")
        screenshot_bytes = int(screenshot["data"]["screenshot"]["bytes"])
        _require(screenshot_bytes > 0, "screenshot evidence was empty")
        return {
            "coordinate_actionability": actionability,
            "screenshot_bytes": screenshot_bytes,
        }
    if scenario == "transformed_3d":
        actionability = _actionability(by_id, "transformed-widget")
        _require(
            actionability == "transformed_3d",
            "3D frame did not stop coordinate interaction",
        )
        screenshot = await client.call("page_screenshot")
        return {
            "coordinate_actionability": actionability,
            "screenshot_bytes": screenshot["data"]["screenshot"]["bytes"],
        }

    frame_id = {
        "normal": "normal-widget",
        "below_viewport": "below-widget",
        "delayed_mount": "delayed-widget",
    }[scenario]
    selector = f"#{frame_id}"
    initial = _actionability(by_id, frame_id)
    if scenario == "below_viewport":
        _require(initial == "off_viewport", "below frame started inside viewport")
    else:
        _require(initial == "ready", f"{scenario} frame was not actionable")

    scrolled = await client.call(
        "element_scroll_into_view",
        {"selector": selector, "center": True, "timeout": 3},
    )
    after = scrolled["data"]["after"]
    _require(after["in_viewport"] is True, "frame remained outside viewport")
    _require(
        after["rect"]["viewport_coordinate_space"] == "top_level_viewport",
        "frame coordinates were not top-level viewport coordinates",
    )
    state = await client.call(
        "element_state_get", {"selector": selector, "timeout": 3}
    )
    location = state["data"]["rect"]["viewport_location"]
    geometry = await client.call(
        "page_evaluate",
        {
            "script": (
                f"const r=document.querySelector('{selector}').getBoundingClientRect();"
                "return {x:r.left,y:r.top};"
            )
        },
    )
    observed = geometry["data"]["result"]
    error_px = max(
        abs(float(location["x"]) - float(observed["x"])),
        abs(float(location["y"]) - float(observed["y"])),
    )
    _require(error_px <= 1.0, f"geometry error was {error_px:.3f}px")
    await client.call(
        "page_click_xy",
        {
            "x": location["x"] + 32,
            "y": location["y"] + 32,
            "element": "fixture cross-origin challenge control",
        },
    )
    expected = frame_id.removesuffix("-widget") + ":passed"
    await client.call(
        "wait_until",
        {
            "condition": "text_contains",
            "selector": "#challenge-status",
            "value": expected,
            "timeout": 3,
        },
    )
    postcondition = await client.call(
        "element_get_text", {"selector": "#challenge-status"}
    )
    value = str(postcondition["data"]["text"])
    _require(value == expected, f"unexpected parent postcondition: {value}")
    screenshot = await client.call("page_screenshot")
    screenshot_bytes = int(screenshot["data"]["screenshot"]["bytes"])
    _require(screenshot_bytes > 0, "screenshot evidence was empty")
    return {
        "first_geometry_error_px": round(error_px, 3),
        "coordinate_actionability": "ready",
        "postcondition": value,
        "screenshot_bytes": screenshot_bytes,
    }


def _actionability(frames: dict[str, dict[str, Any]], frame_id: str) -> str:
    try:
        return str(frames[frame_id]["outer"]["presentation"]["coordinate_actionability"])
    except KeyError as exc:
        raise ChallengeBenchmarkFailure(f"missing frame evidence: {frame_id}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ChallengeBenchmarkFailure(message)


def _summarize(runs: list[dict[str, Any]], iterations: int) -> dict[str, Any]:
    required = ceil(iterations * 0.9)
    scenarios: dict[str, dict[str, Any]] = {}
    for scenario in SCENARIOS:
        selected = [item for item in runs if item["scenario"] == scenario]
        successes = sum(bool(item["success"]) for item in selected)
        geometry_errors = [
            float(item["first_geometry_error_px"])
            for item in selected
            if item.get("first_geometry_error_px") is not None
        ]
        scenarios[scenario] = {
            "successes": successes,
            "runs": len(selected),
            "success_rate": round(successes / len(selected), 3) if selected else 0.0,
            "passed": successes >= required,
            "tool_calls": sum(int(item["tool_call_count"]) for item in selected),
            "max_first_geometry_error_px": (
                max(geometry_errors) if geometry_errors else None
            ),
        }
    return {
        "passed": all(item["passed"] for item in scenarios.values()),
        "total_runs": len(runs),
        "successful_runs": sum(bool(item["success"]) for item in runs),
        "scenarios": scenarios,
    }


def _failure_category(error: str) -> str:
    lowered = error.lower()
    if any(name in lowered for name in ("browser", "chrome", "chromium")):
        return "browser_unavailable"
    if "geometry" in lowered or "viewport" in lowered:
        return "geometry_mismatch"
    if "postcondition" in lowered or "condition" in lowered:
        return "postcondition_failed"
    return "scenario_failure"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    report = asyncio.run(run_benchmark(args.iterations))
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    else:
        print(encoded, end="")
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
