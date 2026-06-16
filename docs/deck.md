# Quorum — Submission Deck (5 slides)

> Use case: **Agentic KYC / AGENTS_002 (Track 1 — Agents)**, TCS × AMD AI Hackathon.
> Tagline: *"We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom."*
> All numbers below are from the real run on an AMD Instinct MI300X (see `eval/results.json`, `bench/results/`).

---

## Slide 1 — Basic Information

**Quorum — a verifiable decision engine for KYC/fraud approvals**

- **Team / Individual:** <YOUR NAME / TEAM NAME>  ·  Roles: <e.g. Pratiksha Gayen — build, eval, GPU>
- **Use case / Challenge:** Agentic KYC onboarding decisions — **AGENTS_002**
- **One-liner:** A jury of diverse LLM personas deliberates each KYC case in parallel on a single AMD GPU; an adjudicator combines their verdicts into APPROVE / REJECT / ESCALATE with a confidence score and a full dissent audit trail.
- **Tagline:** *We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom.*

---

## Slide 2 — Problem & Context

**A single LLM is a confident, unauditable single point of failure.**

- KYC/onboarding approvals are high-stakes: a wrong APPROVE onboards a fraudster; a wrong REJECT loses a real customer. Both carry **regulatory and financial** penalties.
- A solo LLM **hallucinates, is overconfident, and leaves no record of *why*** — unacceptable for a regulated compliance decision that must be defensible to an auditor.
- **Our evidence:** on 151 cases, a single strong model (Qwen2.5-7B) **confidently approved 57% of the bad actors it should have caught** (recall 0.43) — and gave no dissenting view to flag the risk.
- **Stakeholders:** compliance & risk teams, auditors/regulators, and the customers wrongly blocked or wrongly onboarded.

---

## Slide 3 — Solution Overview

**Consensus-as-verification: a jury + adjudicator, not one oracle.**

```
                         ┌─────────────────────────────────────────┐
   KYC case ─────────────►   3 jurors run IN PARALLEL on ONE GPU    │
   (profile +            │   • Compliance Officer   (temp 0.2)      │
    narrative)           │   • Risk Analyst         (temp 0.5)      │
        │                │   • Devil's Advocate     (temp 0.8)      │
        │                └────────────────────┬────────────────────┘
        │                                     │ structured JSON verdicts
        │                                     ▼
        │                ┌─────────────────────────────────────────┐
        │                │  ADJUDICATOR (deterministic)            │
        │                │  majority vote · agreement ratio ·      │
        │                │  panel confidence → APPROVE / REJECT /  │
        │                │  ESCALATE  +  dissent report (audit)    │
        │                └─────────────────────────────────────────┘
        │
        └──► Baseline single model (1 call) ── for side-by-side comparison
```

- **AI approach:** multi-agent **consensus**, prompt-induced diversity (one model, distinct personas + temperatures), **reason-then-decide** structured output, **RAG-free** (decision is pure reasoning over the case).
- **Reliability built in:** strict JSON parse + retry + `ABSTAIN` fallback; principled **ESCALATE** when the panel genuinely splits — so ambiguous cases go to a human instead of an overconfident guess.
- **Stack:** **vLLM** (ROCm) for inference · **FastAPI** backend · **Next.js** dashboard.
- **Built during the hackathon:** the entire system — jurors, orchestrator, adjudicator, eval + AMD benchmark harnesses, the synthesized labeled dataset, and the dashboard. No prior/proprietary code reused; models are open-weight.

---

## Slide 4 — Model Insights (the numbers)

**Model & infra**
- Model: **Qwen/Qwen2.5-7B-Instruct** (open-weight), served on **vLLM (ROCm)**, one model / three personas + a baseline.
- Hardware: **1 × AMD Instinct MI300X** (gfx942). **~165 GiB of 192 GiB VRAM used (~86%)** during the benchmark — the whole jury fits on a single GPU.
- Dataset: **151 synthesized, labeled KYC cases** (70 APPROVE / 81 REJECT) across four difficulty bands — *fully synthetic & non-proprietary, no customer data* (synthesis in `eval/prepare_data.py`).

**Baseline (solo model) vs Quorum council**

| Metric | Baseline | Council |
|---|---|---|
| Accuracy | 0.695 | **0.98** |
| Recall (catch bad actors) | 0.432 | **0.963** |
| Precision (don't block good ones) | 1.00 | **1.00** |
| Tokens / decision | 310 | 1,209 |
| Latency p50 / p95 | — | 961 / 1,279 ms |

- **Headline — Contradiction-catch rate 0.285: in 43 of 151 cases the *confident* baseline was wrong and the council corrected it.**
- The council catches **96%** of bad actors vs the solo model's **43%**, while still blocking **zero** clean customers (precision 1.0).
- **ESCALATE:** 29/151 (~19%) routed to a human — all on genuine REJECT-risk cases, **never on clean ones**.

**AMD concurrency benchmark** — insert chart `bench/results/throughput.png`
- Running the jury **in parallel vs one-at-a-time: 56.9 vs 36.7 decisions/min → 1.55× throughput**, p95 latency 1,377 vs 2,050 ms. The diverse panel costs ~3× the tokens of a solo call but runs concurrently on one GPU.

> **Disclosure (honesty):** dataset is synthetic (method in repo). Council accuracy counts an ESCALATE as "correct" (it avoided a wrong auto-decision); the model-independent claims are **recall 0.43→0.96** and **catch-rate 0.285**.

---

## Slide 5 — Impact & Demo Summary

**Impact**
- **Fewer fraudulent approvals** (recall 0.43 → 0.96) **with no increase in false rejections** (precision stays 1.0) — directly fewer onboarded bad actors and fewer lost good customers.
- **Auditable by construction:** every decision ships a confidence score + a verbatim **dissent report** — the "why" a regulator demands.
- **Right-sizes human effort:** auto-decides the clear cases, **escalates only the genuinely ambiguous ~19%** to a reviewer.

**Key differentiator**
- **Consensus-as-verification on a single AMD Instinct GPU** — the diversity + dissent + escalation, not a bigger model, is what makes the decision trustworthy.

**Demo flow (≈60s)**
1. Open the dashboard on the planted case `DEMO-FRAUD` — reads clean and professional.
2. Single model → **APPROVE**, high confidence. "A solo LLM waves a layering pattern through."
3. The jury → splits; the compliance officer & devil's advocate flag the pass-through / income mismatch → adjudicator returns **ESCALATE with the dissent on record**.
4. "The solo model would have onboarded it. The council caught it *and produced the audit trail* — on one AMD GPU, in parallel."
5. Cut to Slide 4: accuracy lift + catch-rate + the AMD throughput chart.

**Future work**
- Multi-model council (Option B — the 192 GB MI300X easily holds 3+ models); an LLM **chief-judge** adjudicator; more/specialized jurors; domain fine-tuned jurors; real labeled case data.
