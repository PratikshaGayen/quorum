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
        if "general-purpose" in persona:            # the single-model baseline: over-trusting
            risk_score -= 3
        elif "devil" in persona and risk_score >= 1:  # amplifies existing doubt only
            risk_score += 1

        if risk_score >= 2:
            decision = "REJECT"
            confidence = min(0.95, 0.7 + 0.05 * risk_score + rng.uniform(0, 0.1))
            rationale = (
                f"Risk signals outweigh the reassuring framing ({', '.join(band_flags[:2]) or 'behavioral anomalies'}). "
                "Evidence does not support onboarding."
            )
            flags = band_flags[:4]
        elif risk_score <= 0:
            decision = "APPROVE"
            confidence = min(0.95, 0.75 + rng.uniform(0, 0.15))
            rationale = "Profile reads consistent; nothing in the narrative looks materially wrong at face value."
            flags = []
        else:
            decision = rng.choice(["APPROVE", "REJECT"])
            confidence = 0.5 + rng.uniform(0, 0.15)
            rationale = "Evidence is mixed; some indicators are concerning but not conclusive."
            flags = band_flags[:2]
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
