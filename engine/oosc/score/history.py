"""Persistent reliability history across CI invocations and commits."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oosc.score.scorecard import Scorecard


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "no-git"


def previous_snapshot(history_dir: Path, domain: str) -> tuple[Path | None, dict[str, Any] | None]:
    for path in sorted(history_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("domain") == domain:
            return path, data
    return None, None


def compare_snapshots(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"baseline": None, "comparisons": {}, "gate_pass": True}
    comparisons = {}
    for name, candidate in current.get("scorecards", {}).items():
        base = previous.get("scorecards", {}).get(name)
        if not base:
            continue
        detail = Scorecard.regression(base, candidate)
        detail["overall_delta"] = round(
            candidate.get("overall", {}).get("reliability", 0.0)
            - base.get("overall", {}).get("reliability", 0.0),
            4,
        )
        comparisons[name] = detail
    return {
        "baseline": previous.get("snapshot_id"),
        "comparisons": comparisons,
        "gate_pass": all(item.get("gate_pass", True) for item in comparisons.values()),
    }


def persist_snapshot(history_dir: Path, report: dict[str, Any]) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    snapshot_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{git_sha()}"
    payload = dict(report)
    payload["snapshot_id"] = snapshot_id
    payload["commit_sha"] = git_sha()
    path = history_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path
