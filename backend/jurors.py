"""Council definition + per-juror invocation with strict JSON parsing.

Option A: one base model, N distinct personas (system prompts) at varied
temperatures. Diversity is prompt-induced. The baseline single-model is a
separate, deliberately over-trusting juror used only for the demo comparison.
"""

import json
import re
from dataclasses import dataclass

from . import config
from .inference import InferenceClient
from .schemas import Case, Verdict

# 'rationale' is emitted FIRST so the model reasons through the facts before it
# commits to a decision — essential for catching risk that is implicit, not stated.
_VERDICT_FIELDS = (
    '{"rationale": "<your step-by-step reasoning in <= 3 sentences>", '
    '"flags": ["risk signal", ...], '
    '"decision": "APPROVE" | "REJECT", '
    '"confidence": <float 0.0-1.0>}'
)

# Domain scrutiny a compliance panel applies that a naive single-shot read does
# not. Given to the council jurors only — the baseline stays a plain assistant.
_SCRUTINY = (
    "Judge the specific facts, not the overall impression. Check in particular whether: "
    "stated income is consistent with deposit or transfer volumes; amounts sit just below "
    "regulatory reporting thresholds; funds move in and straight back out (pass-through); "
    "the stated location is inconsistent with where activity originates; or beneficial "
    "ownership is opaque. Do not accept a reassuring framing if the underlying facts conflict. "
)


@dataclass(frozen=True)
class Juror:
    juror_id: str
    persona: str
    system_prompt: str
    temperature: float


def _system_prompt(persona_desc: str, *, scrutiny: bool = False) -> str:
    return (
        f"You are a {persona_desc}. Review the KYC/onboarding case below and reason "
        "through the specifics before deciding. "
        + (_SCRUTINY if scrutiny else "")
        + "Output ONLY valid JSON matching this exact schema, with no prose, no markdown "
        f"fences, nothing else: {_VERDICT_FIELDS}. Fill 'rationale' first (your reasoning), "
        "then 'decision'. Do not invent facts not present in the case. If evidence is "
        "insufficient, lower your confidence."
    )


COUNCIL: list[Juror] = [
    Juror(
        "compliance_officer",
        "strict, rule-focused compliance officer",
        _system_prompt(
            "strict compliance officer who enforces KYC/AML rules to the letter",
            scrutiny=True,
        ),
        0.2,
    ),
    Juror(
        "risk_analyst",
        "pattern- and behaviour-focused risk analyst",
        _system_prompt(
            "risk analyst focused on behavioral patterns and transaction anomalies",
            scrutiny=True,
        ),
        0.5,
    ),
    Juror(
        "devils_advocate",
        "devil's advocate who argues against the obvious read",
        _system_prompt(
            "devil's advocate who deliberately argues the opposite of the obvious "
            "conclusion to surface overlooked risk",
            scrutiny=True,
        ),
        0.8,
    ),
]

# The single-model baseline: one plain assistant call, mirroring a naive solo LLM.
# It gets NO domain scrutiny — that is precisely what the council adds.
BASELINE = Juror(
    "baseline_single_model",
    "general-purpose assistant",
    _system_prompt("helpful general-purpose assistant"),
    0.7,
)


def _case_to_user_prompt(case: Case) -> str:
    return (
        f"CASE {case.case_id}\n"
        f"Profile: {json.dumps(case.profile)}\n"
        f"Narrative: {case.narrative}"
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    # Grab the outermost JSON object if the model wrapped it in prose.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else text


def _parse_verdict(juror_id: str, raw: str, tokens: int, latency_ms: float) -> Verdict:
    data = json.loads(_strip_fences(raw))
    return Verdict(
        juror_id=juror_id,
        decision=data["decision"],
        confidence=float(data["confidence"]),
        rationale=data.get("rationale", ""),
        flags=list(data.get("flags", [])),
        tokens_used=tokens,
        latency_ms=latency_ms,
    )


async def run_juror(client: InferenceClient, juror: Juror, case: Case) -> Verdict:
    """Invoke one juror. Strict parse + one retry, then ABSTAIN fallback."""
    user = _case_to_user_prompt(case)
    last_tokens, last_latency = 0, 0.0
    for attempt in range(config.PARSE_RETRIES + 1):
        seed = 1000 + attempt
        raw, tokens, latency_ms = await client.complete(
            config.PRIMARY_MODEL, juror.system_prompt, user, juror.temperature, seed
        )
        last_tokens, last_latency = tokens, latency_ms
        try:
            return _parse_verdict(juror.juror_id, raw, tokens, latency_ms)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return Verdict(
        juror_id=juror.juror_id,
        decision="ABSTAIN",
        confidence=0.0,
        rationale="Could not produce a schema-valid verdict after retry.",
        flags=["parse_failure"],
        tokens_used=last_tokens,
        latency_ms=last_latency,
    )
