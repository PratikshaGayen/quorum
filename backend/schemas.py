"""Pydantic contracts shared across the whole engine.

These are the single source of truth: a Case goes in, jurors emit Verdicts,
the adjudicator emits one Decision. Everything else depends on these types.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Case(BaseModel):
    """One record to be decided."""

    case_id: str
    profile: dict  # structured fields (name, country, account age, etc.)
    narrative: str  # free-text description / activity summary
    # ground_truth is held out of what jurors see; used only by eval.
    ground_truth: Optional[Literal["APPROVE", "REJECT"]] = None


class Verdict(BaseModel):
    """One juror's output. Must be strict JSON, no prose around it."""

    juror_id: str
    decision: Literal["APPROVE", "REJECT", "ABSTAIN"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str  # <= 3 sentences
    flags: list[str] = Field(default_factory=list)  # risk signals cited
    tokens_used: int = 0
    latency_ms: float = 0.0


class Decision(BaseModel):
    """Adjudicator output — the auditable artifact."""

    case_id: str
    final_decision: Literal["APPROVE", "REJECT", "ESCALATE"]
    panel_confidence: float = Field(ge=0.0, le=1.0)
    agreement_ratio: float = Field(ge=0.0, le=1.0)  # fraction agreeing with majority
    dissent_report: list[Verdict] = Field(default_factory=list)  # minority opinions
    all_verdicts: list[Verdict] = Field(default_factory=list)
    rationale_summary: str
    # baseline single-model verdict, for the side-by-side demo comparison.
    baseline_verdict: Optional[Verdict] = None
    total_tokens: int = 0
    total_latency_ms: float = 0.0
