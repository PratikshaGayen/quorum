"""Lightweight metrics: per-decision JSONL logging + run summaries.

No external deps beyond stdlib so it runs anywhere. run_eval.py uses
summarize() to build the Slide-4 comparison.
"""

import json
from pathlib import Path
from statistics import mean

from .schemas import Decision


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def log_decision(decision: Decision, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(decision.model_dump_json() + "\n")


def latency_summary(latencies: list[float]) -> dict:
    return {
        "p50_ms": round(percentile(latencies, 0.50), 1),
        "p95_ms": round(percentile(latencies, 0.95), 1),
        "mean_ms": round(mean(latencies), 1) if latencies else 0.0,
    }
