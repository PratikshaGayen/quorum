"""Inference clients behind one interface.

MockClient runs the entire pipeline with no GPU (Phase 0/2 dev).
VLLMClient talks to a vLLM OpenAI-compatible server (GPU phases).
config.USE_MOCK picks one via get_client().
"""

import asyncio
import json
import random
import time
from abc import ABC, abstractmethod

from . import config


class InferenceClient(ABC):
    @abstractmethod
    async def complete(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        seed: int,
    ) -> tuple[str, int, float]:
        """Return (text, tokens_used, latency_ms)."""
        raise NotImplementedError


class VLLMClient(InferenceClient):
    """Calls the vLLM OpenAI-compatible chat endpoint via httpx (async)."""

    def __init__(self) -> None:
        import httpx  # imported lazily so laptops without it can still run mock

        self._client = httpx.AsyncClient(
            base_url=config.VLLM_BASE_URL,
            headers={"Authorization": f"Bearer {config.VLLM_API_KEY}"},
            timeout=120.0,
        )

    async def complete(self, model, system, user, temperature, seed):
        t0 = time.perf_counter()
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "seed": seed,
                "max_tokens": config.MAX_TOKENS,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000
        text = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return text, tokens, latency_ms

    async def aclose(self) -> None:
        await self._client.aclose()


class MockClient(InferenceClient):
    """Returns plausible structured verdicts without a GPU.

    The decision is derived deterministically from risk signals in the case
    narrative so the mock pipeline behaves realistically: clean cases tend to
    APPROVE, risky ones tend to REJECT, and the planted demo case fools a
    'gullible' persona while the strict personas catch it.
    """

    RISK_TERMS = (
        "sanction",
        "shell company",
        "mismatch",
        "no source of funds",
        "structuring",
        "pep",
        "high-risk jurisdiction",
        "forged",
        "stolen",
        "anonymous",
    )

    async def complete(self, model, system, user, temperature, seed):
        t0 = time.perf_counter()
        # Deterministic-but-varied jitter keyed on persona + case content.
        rng = random.Random(f"{system[:40]}|{user}|{seed}")

        # Map the synthesized case bands (encoded in the case_id, which is part of
        # the prompt) to a base risk, so the mock reproduces the real model's
        # behaviour offline: clean -> approve; subtle/blatant -> the strict jurors
        # reject while the lenient baseline is fooled; ambiguous -> a split.
        text_l = user.lower()
        keyword_hits = [t for t in self.RISK_TERMS if t in text_l]
        if "clean-" in text_l:
            risk_score, band_flags = 0, []
        elif "ambig-" in text_l:
            risk_score, band_flags = 1, ["conflicting signals", "needs human review"]
        elif "subtle-" in text_l or "demo-fraud" in text_l:
            risk_score = 2
            band_flags = ["activity inconsistent with stated income",
                          "rapid pass-through of funds", "opaque counterparties"]
        elif "blat-" in text_l:
            risk_score, band_flags = 2, keyword_hits
        else:  # ad-hoc case (e.g. typed in by hand): fall back to keyword detection
            risk_score, band_flags = len(keyword_hits), keyword_hits

        persona = system.lower()
        if "compliance officer" in persona:
            role = "compliance"
        elif "risk analyst" in persona:
            role = "risk"
        elif "devil" in persona:
            role = "devil"
        else:
            role = "baseline"

        if role == "baseline":              # the single-model baseline: over-trusting
            risk_score -= 3
        elif role == "devil" and risk_score >= 1:  # amplifies existing doubt only
            risk_score += 1

        # Each council persona fixates on a different facet of the case and frames
        # it in its own voice, so the cards read distinctly — mirroring the real
        # model's diverse reasoning rather than three identical clones.
        primary = band_flags[{"compliance": 0, "risk": 1, "devil": 2}.get(role, 0) % len(band_flags)] if band_flags else "the documented red flag"
        role_flag = {"compliance": "regulatory threshold", "risk": "pattern anomaly", "devil": "unverified assumption"}.get(role)

        if risk_score >= 2:
            decision = "REJECT"
            confidence = min(0.95, 0.7 + 0.05 * risk_score + rng.uniform(0, 0.1))
            rationale = {
                "compliance": f"This fails KYC/AML on the facts — {primary}. Onboarding cannot proceed without remediation.",
                "risk": f"The activity pattern is anomalous: {primary}, inconsistent with the stated profile.",
                "devil": f"Even on a charitable reading, {primary} is unexplained — the reassuring framing is doing too much work.",
            }.get(role, f"Risk signals outweigh the framing ({primary}).")
            flags = [f for f in (primary, role_flag) if f]
        elif risk_score <= 0:
            decision = "APPROVE"
            confidence = min(0.95, 0.75 + rng.uniform(0, 0.15))
            rationale = {
                "baseline": "The profile looks professional and the paperwork appears in order; I see no clear reason to decline.",
                "compliance": "Documentation satisfies KYC requirements; no rule violation identified.",
                "risk": "Transaction behaviour matches the stated profile; no anomalies detected.",
                "devil": "I looked for a reason to decline but found no concrete red flag.",
            }.get(role, "No material risk signals found.")
            flags = []
        else:
            decision = rng.choice(["APPROVE", "REJECT"])
            confidence = 0.5 + rng.uniform(0, 0.15)
            rationale = {
                "compliance": f"Borderline — {primary} warrants scrutiny but isn't a clear violation.",
                "risk": f"Mixed signals: {primary} is concerning but not conclusive.",
                "devil": f"I'd flag {primary}, though the case for rejection is thin.",
            }.get(role, "Evidence is mixed.")
            flags = [primary]
        payload = {
            "decision": decision,
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "flags": flags,
        }
        # Simulate a realistic per-call latency so concurrency wins are visible.
        # asyncio.sleep (not time.sleep) yields the loop so asyncio.gather overlaps.
        await asyncio.sleep(rng.uniform(0.05, 0.15))
        latency_ms = (time.perf_counter() - t0) * 1000
        tokens = len(user) // 4 + len(json.dumps(payload)) // 4
        return json.dumps(payload), tokens, latency_ms


def get_client() -> InferenceClient:
    return MockClient() if config.USE_MOCK else VLLMClient()
