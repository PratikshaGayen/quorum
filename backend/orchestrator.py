"""Async fan-out to the jury + baseline, then adjudication.

deliberate() runs all jurors AND the baseline concurrently via asyncio.gather.
deliberate_sequential() exists only so the benchmark can show the concurrency win.
"""

import asyncio
import time

from .adjudicator import adjudicate
from .inference import InferenceClient, get_client
from .jurors import BASELINE, COUNCIL, Juror, run_juror
from .schemas import Case, Decision, Verdict


async def _run_all(client: InferenceClient, case: Case) -> tuple[list[Verdict], Verdict]:
    *juror_verdicts, baseline = await asyncio.gather(
        *(run_juror(client, j, case) for j in COUNCIL),
        run_juror(client, BASELINE, case),
    )
    return list(juror_verdicts), baseline


async def deliberate(case: Case, client: InferenceClient | None = None) -> Decision:
    own = client is None
    client = client or get_client()
    try:
        t0 = time.perf_counter()
        verdicts, baseline = await _run_all(client, case)
        decision = adjudicate(case.case_id, verdicts, baseline)
        decision.total_latency_ms = (time.perf_counter() - t0) * 1000
        return decision
    finally:
        if own and hasattr(client, "aclose"):
            await client.aclose()


async def deliberate_sequential(case: Case, client: InferenceClient | None = None) -> Decision:
    """Same work, one juror at a time — for the benchmark comparison only."""
    own = client is None
    client = client or get_client()
    try:
        t0 = time.perf_counter()
        verdicts = [await run_juror(client, j, case) for j in COUNCIL]
        baseline = await run_juror(client, BASELINE, case)
        decision = adjudicate(case.case_id, verdicts, baseline)
        decision.total_latency_ms = (time.perf_counter() - t0) * 1000
        return decision
    finally:
        if own and hasattr(client, "aclose"):
            await client.aclose()
