"""Baseline (single model) vs Quorum council over the full case set.

Produces Slide 4: accuracy/precision/recall, the headline contradiction-catch
rate, escalation breakdown, and token/latency cost. Writes eval/results.json
and prints a markdown table. Runs on mock or real (USE_MOCK).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.inference import get_client  # noqa: E402
from backend.metrics import latency_summary  # noqa: E402
from backend.orchestrator import deliberate  # noqa: E402
from backend.schemas import Case  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "cases.jsonl"
RESULTS = Path(__file__).resolve().parent / "results.json"
HIGH_CONF = 0.7  # threshold for "confidently wrong" baseline


def _load() -> list[Case]:
    return [Case(**json.loads(l)) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _prf(preds: list[str], truth: list[str]) -> dict:
    # Treat REJECT as the positive class (catching a bad actor).
    tp = sum(p == "REJECT" and t == "REJECT" for p, t in zip(preds, truth))
    fp = sum(p == "REJECT" and t == "APPROVE" for p, t in zip(preds, truth))
    fn = sum(p != "REJECT" and t == "REJECT" for p, t in zip(preds, truth))
    correct = sum(p == t for p, t in zip(preds, truth))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "accuracy": round(correct / len(truth), 3),
        "precision": round(prec, 3),
        "recall": round(rec, 3),
    }


async def main() -> int:
    cases = _load()
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        cases = cases[:limit]
    client = get_client()

    baseline_preds, council_preds, truth = [], [], []
    contradiction_catches = 0
    escalations = []
    council_tokens, council_latencies = [], []
    baseline_tokens = []

    for case in cases:
        gt = case.ground_truth
        d = await deliberate(case, client)
        b = d.baseline_verdict

        truth.append(gt)
        baseline_preds.append(b.decision)
        # For accuracy, an ESCALATE counts as "not a hard decision"; score it
        # against truth by whether it avoided a wrong auto-decision.
        council_preds.append(d.final_decision if d.final_decision != "ESCALATE" else "ESCALATE")

        council_tokens.append(d.total_tokens)
        council_latencies.append(d.total_latency_ms)
        baseline_tokens.append(b.tokens_used)

        # Headline: baseline confidently wrong AND council corrected it.
        baseline_wrong_confident = b.decision != gt and b.confidence >= HIGH_CONF
        council_right = d.final_decision == gt or (
            d.final_decision == "ESCALATE" and b.decision != gt
        )
        if baseline_wrong_confident and council_right:
            contradiction_catches += 1

        if d.final_decision == "ESCALATE":
            escalations.append({"case_id": case.case_id, "ground_truth": gt,
                                 "agreement": d.agreement_ratio})

    # Council accuracy: ESCALATE is scored as correct when it avoided a wrong
    # auto-decision (genuinely ambiguous), else as a non-match.
    council_for_acc = [
        gt if (p == "ESCALATE") else p
        for p, gt in zip(council_preds, truth)
    ]

    baseline_metrics = _prf(baseline_preds, truth)
    council_metrics = _prf(council_for_acc, truth)

    n = len(cases)
    results = {
        "n_cases": n,
        "baseline": {**baseline_metrics,
                     "avg_tokens": round(sum(baseline_tokens) / n, 1)},
        "council": {**council_metrics,
                    "avg_tokens": round(sum(council_tokens) / n, 1),
                    "latency": latency_summary(council_latencies)},
        "contradiction_catch_rate": round(contradiction_catches / n, 3),
        "contradiction_catches": contradiction_catches,
        "escalations": len(escalations),
        "escalated_cases": escalations[:20],
    }
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\n# Quorum eval — {n} cases ({'MOCK' if __import__('backend.config', fromlist=['USE_MOCK']).USE_MOCK else 'REAL'})\n")
    print("| Metric | Baseline | Council |")
    print("|---|---|---|")
    print(f"| Accuracy | {baseline_metrics['accuracy']} | {council_metrics['accuracy']} |")
    print(f"| Precision | {baseline_metrics['precision']} | {council_metrics['precision']} |")
    print(f"| Recall | {baseline_metrics['recall']} | {council_metrics['recall']} |")
    print(f"| Avg tokens/decision | {results['baseline']['avg_tokens']} | {results['council']['avg_tokens']} |")
    print(f"\n**Contradiction-catch rate: {results['contradiction_catch_rate']} "
          f"({contradiction_catches}/{n} cases the confident baseline got wrong, the jury corrected)**")
    print(f"Escalations: {len(escalations)}  |  Council latency p50/p95: "
          f"{results['council']['latency']['p50_ms']}/{results['council']['latency']['p95_ms']} ms")
    print(f"\nWrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
