"""Reliability scorecard: rates with Wilson 95% intervals, by category,
comparable across agent versions. Reliability is never a single pass/fail."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def wilson_interval(successes: int, trials: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval - honest under small trials, never degenerate."""
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


@dataclass
class CategoryRate:
    category: str
    runs: int = 0
    successes: int = 0
    failures_by_kind: dict[str, int] = field(default_factory=dict)

    def record(self, success: bool, failure_kinds: list[str] | None = None):
        self.runs += 1
        if success:
            self.successes += 1
        for k in failure_kinds or []:
            self.failures_by_kind[k] = self.failures_by_kind.get(k, 0) + 1

    def to_dict(self) -> dict:
        lo, hi = wilson_interval(self.successes, self.runs)
        rate = self.successes / self.runs if self.runs else 0.0
        return {
            "category": self.category,
            "runs": self.runs,
            "successes": self.successes,
            "reliability": round(rate, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "failures_by_kind": dict(sorted(self.failures_by_kind.items())),
        }


class Scorecard:
    def __init__(self, agent_version: str, generated_at: str = ""):
        self.agent_version = agent_version
        self.generated_at = generated_at
        self.categories: dict[str, CategoryRate] = {}

    def record(self, category: str, success: bool, failure_kinds: list[str] | None = None):
        cr = self.categories.setdefault(category, CategoryRate(category))
        cr.record(success, failure_kinds)

    def to_dict(self) -> dict:
        overall_runs = sum(c.runs for c in self.categories.values())
        overall_ok = sum(c.successes for c in self.categories.values())
        lo, hi = wilson_interval(overall_ok, overall_runs)
        return {
            "agent_version": self.agent_version,
            "generated_at": self.generated_at,
            "overall": {
                "runs": overall_runs,
                "successes": overall_ok,
                "reliability": round(overall_ok / overall_runs, 4) if overall_runs else 0.0,
                "ci95": [round(lo, 4), round(hi, 4)],
            },
            "categories": [c.to_dict() for c in sorted(self.categories.values(), key=lambda x: x.category)],
        }

    @staticmethod
    def regression(base: dict, candidate: dict) -> dict:
        """Category-level comparison of two scorecards: delta of reliability
        with interval overlap check - a drop is significant only when the
        candidate's upper bound falls below the base's lower bound."""
        base_cats = {c["category"]: c for c in base.get("categories", [])}
        out = []
        for c in candidate.get("categories", []):
            b = base_cats.get(c["category"])
            if not b:
                continue
            delta = round(c["reliability"] - b["reliability"], 4)
            significant_regression = c["ci95"][1] < b["ci95"][0]
            out.append(
                {
                    "category": c["category"],
                    "base": b["reliability"],
                    "candidate": c["reliability"],
                    "delta": delta,
                    "significant_regression": significant_regression,
                }
            )
        return {"regressions": out, "gate_pass": not any(r["significant_regression"] for r in out)}
