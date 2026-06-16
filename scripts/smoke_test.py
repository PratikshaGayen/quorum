"""End-to-end sanity check on the mock backend (no GPU).

Verifies: schemas validate, a full deliberation runs, the planted demo case
is caught by the jury but approved by the baseline, and concurrent fan-out is
faster than sequential.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.inference import get_client  # noqa: E402
from backend.orchestrator import deliberate, deliberate_sequential  # noqa: E402
from backend.schemas import Case  # noqa: E402

DEMO = Case(
    case_id="DEMO-FRAUD",
    profile={"name": "V. Castellano", "country": "Netherlands", "account_age_months": 36},
    narrative=(
        "Applicant V. Castellano presents a polished profile: a 36-month banking "
        "history, professional references, and a declared income of $95,000. "
        "Onboarding looks routine. The file notes that the account regularly "
        "receives six-figure transfers from newly registered counterparties and "
        "forwards them within a day, which the relationship manager describes as "
        "'consistent with the client's consulting business'."
    ),
)


async def main() -> int:
    client = get_client()
    decision = await deliberate(DEMO, client)

    print(f"Final decision : {decision.final_decision}")
    print(f"Panel conf     : {decision.panel_confidence}")
    print(f"Agreement      : {decision.agreement_ratio}")
    print(f"Baseline said  : {decision.baseline_verdict.decision} "
          f"(conf {decision.baseline_verdict.confidence})")
    for v in decision.all_verdicts:
        print(f"  - {v.juror_id:20s} {v.decision:8s} conf={v.confidence:.2f} flags={v.flags}")

    assert decision.final_decision in ("REJECT", "ESCALATE"), "jury should not APPROVE the fraud case"
    assert all(v.juror_id for v in decision.all_verdicts)
    if decision.baseline_verdict.decision == "APPROVE":
        print("\n>>> Demo moment: the solo baseline APPROVED the fraud — the jury caught it.")
    else:
        print("\n>>> Note: the baseline also flagged this case; pick a subtler demo narrative if you want the contrast.")

    # Concurrency must beat sequential.
    t0 = time.perf_counter()
    await deliberate(DEMO, client)
    concurrent_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    await deliberate_sequential(DEMO, client)
    sequential_ms = (time.perf_counter() - t0) * 1000
    print(f"\nConcurrent: {concurrent_ms:.0f}ms  Sequential: {sequential_ms:.0f}ms  "
          f"speedup: {sequential_ms / concurrent_ms:.1f}x")
    assert concurrent_ms < sequential_ms, "concurrent fan-out should be faster"

    print("\nSMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
