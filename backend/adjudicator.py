"""Deterministic adjudication: combine juror verdicts into one Decision.

Rules (Section 7.4):
- Majority vote over non-abstaining jurors -> tentative decision.
- agreement_ratio = majority_count / voting_jurors.
- panel_confidence = mean(confidence of majority jurors) * agreement_ratio.
- ESCALATE if agreement_ratio < 0.66 OR panel_confidence < 0.6.
- dissent_report = minority verdicts, verbatim.
"""

from collections import Counter

from . import config
from .schemas import Decision, Verdict


def adjudicate(case_id: str, verdicts: list[Verdict], baseline: Verdict | None = None) -> Decision:
    voting = [v for v in verdicts if v.decision in ("APPROVE", "REJECT")]

    if not voting:
        return Decision(
            case_id=case_id,
            final_decision="ESCALATE",
            panel_confidence=0.0,
            agreement_ratio=0.0,
            dissent_report=[],
            all_verdicts=verdicts,
            rationale_summary="No juror produced a valid verdict; escalating to human.",
            baseline_verdict=baseline,
            total_tokens=sum(v.tokens_used for v in verdicts),
            total_latency_ms=max((v.latency_ms for v in verdicts), default=0.0),
        )

    counts = Counter(v.decision for v in voting)
    majority_decision, majority_count = counts.most_common(1)[0]
    agreement_ratio = majority_count / len(voting)

    majority = [v for v in voting if v.decision == majority_decision]
    minority = [v for v in voting if v.decision != majority_decision]
    mean_majority_conf = sum(v.confidence for v in majority) / len(majority)
    panel_confidence = mean_majority_conf * agreement_ratio

    escalate = (
        agreement_ratio < config.ESCALATE_AGREEMENT_BELOW
        or panel_confidence < config.ESCALATE_CONFIDENCE_BELOW
    )
    final = "ESCALATE" if escalate else majority_decision

    summary = " ".join(v.rationale for v in majority).strip()
    if escalate:
        summary = (
            f"Panel split (agreement {agreement_ratio:.0%}, confidence "
            f"{panel_confidence:.0%}) — routed to human review. " + summary
        )

    return Decision(
        case_id=case_id,
        final_decision=final,
        panel_confidence=round(panel_confidence, 3),
        agreement_ratio=round(agreement_ratio, 3),
        dissent_report=minority,
        all_verdicts=verdicts,
        rationale_summary=summary,
        baseline_verdict=baseline,
        total_tokens=sum(v.tokens_used for v in verdicts),
        total_latency_ms=max((v.latency_ms for v in verdicts), default=0.0),
    )
