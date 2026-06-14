"""Concurrent vs sequential juror throughput -> the AMD slide chart.

Runs a fixed set of cases through the council both ways, reports
decisions/min and p95 latency, captures rocm-smi if present (VRAM), and
writes bench/results/benchmark.json (+ a PNG chart if matplotlib is available).

The story: one AMD Instinct GPU runs the whole jury in parallel -> Nx the
throughput of sequential evaluation, at X% VRAM.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.inference import get_client  # noqa: E402
from backend.metrics import percentile  # noqa: E402
from backend.orchestrator import deliberate, deliberate_sequential  # noqa: E402
from backend.schemas import Case  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "eval" / "data" / "cases.jsonl"
OUT = Path(__file__).resolve().parent / "results"
N_CASES = 20


def _load(n: int) -> list[Case]:
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return [Case(**json.loads(l)) for l in lines[:n] if l.strip()]


def _capture_vram() -> str | None:
    try:
        return subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=10
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


async def _timed(coro_fn, cases, client) -> tuple[float, list[float]]:
    latencies = []
    t0 = time.perf_counter()
    for case in cases:
        d = await coro_fn(case, client)
        latencies.append(d.total_latency_ms)
    total_s = time.perf_counter() - t0
    return total_s, latencies


async def main() -> int:
    cases = _load(N_CASES)
    client = get_client()

    seq_s, seq_lat = await _timed(deliberate_sequential, cases, client)
    con_s, con_lat = await _timed(deliberate, cases, client)

    def thru(total_s):  # decisions per minute
        return round(len(cases) / total_s * 60, 1)

    results = {
        "n_cases": len(cases),
        "sequential": {"total_s": round(seq_s, 2), "decisions_per_min": thru(seq_s),
                       "p95_ms": round(percentile(seq_lat, 0.95), 1)},
        "concurrent": {"total_s": round(con_s, 2), "decisions_per_min": thru(con_s),
                       "p95_ms": round(percentile(con_lat, 0.95), 1)},
        "speedup": round(seq_s / con_s, 2),
        "vram_rocm_smi": _capture_vram(),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "benchmark.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.bar(["Sequential", "Concurrent"],
               [results["sequential"]["decisions_per_min"],
                results["concurrent"]["decisions_per_min"]],
               color=["#888", "#e8463a"])
        ax.set_ylabel("Decisions / min")
        ax.set_title(f"Quorum jury on one AMD GPU — {results['speedup']}x throughput")
        fig.tight_layout()
        fig.savefig(OUT / "throughput.png", dpi=120)
        print(f"Chart -> {OUT / 'throughput.png'}")
    except ImportError:
        print("(matplotlib not installed — skipped PNG, JSON still written)")

    print(json.dumps({k: v for k, v in results.items() if k != "vram_rocm_smi"}, indent=2))
    print(f"VRAM capture: {'yes' if results['vram_rocm_smi'] else 'no rocm-smi (not on GPU box)'}")
    print(f"Wrote {OUT / 'benchmark.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
