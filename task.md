# Quorum — Build Specification (A → Z)

> **Project tagline:** *We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom.*

This document is the single source of truth for building **Quorum** for the TCS × AMD AI Hackathon (Track 1 — Agents). Work through it **phase by phase**, top to bottom. Each task has an **acceptance criterion** — do not move on until it's met.

---

## 0. The one-paragraph summary

Quorum is a **verifiable decision engine for high-stakes enterprise approvals** (KYC onboarding / fraud review). Instead of one LLM making an approve/reject call — which hallucinates and isn't auditable — Quorum runs a **panel ("jury") of diverse LLMs in parallel on a single AMD Instinct GPU**. Each juror reviews the same case and returns a structured verdict with reasons and a confidence. An **adjudicator** combines the verdicts into a final decision (`APPROVE` / `REJECT` / `ESCALATE`), a panel-confidence score, and a **dissent report**. The result: every decision ships with an audit trail, and disagreement between jurors catches mistakes a single model would wave through.

**The winning demo moment:** a single model confidently approves a fraudulent case → the Quorum jury catches it → shown side by side, live.

---

## 1. Why this wins (keep this in mind while building)

Scoring rubric (build to optimise this):

| Criterion | Weight | How Quorum scores |
|---|---|---|
| Technical Implementation | **40%** | Real concurrent multi-model inference + adjudication engine, fully working |
| Learnings & Future work | 20% | Clear scalability story (more jurors, bigger panels), measurable gains |
| Innovation & Creativity | 15% | Consensus-as-verification + hardware-justified parallel serving |
| Presentation & Demo Quality | 15% | Dramatic side-by-side "caught hallucination" demo |
| Problem Definition & Relevance | 10% | "Trust & auditability of AI decisions in regulated workflows" — unimpeachable |

**Two differentiators competitors will miss:**
1. **AMD-specific architecture.** Instinct GPUs have large VRAM (e.g. MI300X = 192GB). That lets us co-locate several models and run the whole jury concurrently on **one** GPU — something you can't do on a small card. We benchmark this and put the chart on Slide 4. AMD judges reward it.
2. **Consensus / jury adjudication** — a mechanism most teams won't attempt, and one we can build deeper and faster than anyone copying the pitch.

---

## 2. Mapped hackathon use case

Primary mapping: **AGENTS_002 — Agentic KYC Intelligence Platform** (explicitly references AMD ROCm, multi-agent, explainable, human-in-the-loop). Fraud framing (FINETUNING_003 / general fraud) is an acceptable alternative if the dataset is stronger.

Decision the engine makes per case: **APPROVE / REJECT / ESCALATE-TO-HUMAN**, with confidence + rationale + dissent.

---

## 3. Architecture

```
                         ┌──────────────────────────────┐
   Case (JSON) ─────────▶│        FastAPI backend        │
                         │   (orchestrator, async)       │
                         └───────────────┬──────────────┘
                                         │ fan-out (async, parallel)
              ┌──────────────┬───────────┼───────────┬──────────────┐
              ▼              ▼            ▼            ▼              ▼
          Juror 1        Juror 2      Juror 3      Juror N        (baseline:
        (model/persona) (model/...)  (model/...)  (model/...)     single model)
              │              │            │            │
              └──────────────┴─────┬──────┴────────────┘
                                   ▼
                         ┌──────────────────────┐
                         │      Adjudicator      │  ← aggregates verdicts
                         │  decision + conf +    │
                         │  dissent + routing    │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │   Next.js dashboard   │  ← live deliberation view
                         └──────────────────────┘

   All jurors served by vLLM on AMD ROCm, co-located in one GPU's VRAM.
```

**Juror diversity — two build options:**
- **Option A (default, always works):** one vLLM server + one strong base model; N jurors = N distinct **personas** (system prompts) with varied temperature/seed (e.g. "Skeptical Compliance Officer", "Risk Analyst", "Devil's Advocate"). Diversity is prompt-induced. Cheap, fast, robust.
- **Option B (upgrade if VRAM/time allow):** 2–3 separate vLLM servers, each serving a **different open model** (e.g. Qwen2.5-7B, Llama-3.1-8B, Mistral-7B) running concurrently on the same GPU. Stronger "many models, one AMD GPU" story.

Build Option A first; upgrade to B in Phase 3 only if the first GPU window confirms enough VRAM.

---

## 4. Tech stack

- **Backend / orchestration:** Python 3.11+, FastAPI, `httpx` (async), `pydantic` v2.
- **Inference:** vLLM (OpenAI-compatible server) on AMD ROCm — the handbook's default `ROCm + vLLM` environment.
- **Models (open-source, public weights):** Qwen2.5-7B-Instruct (primary), Llama-3.1-8B-Instruct, optionally Mistral-7B-Instruct.
- **Frontend:** Next.js (App Router) + Tailwind. Single dashboard page.
- **Eval / metrics:** Python (`pandas`, `scikit-learn` for accuracy/precision/recall), simple JSON logs.
- **Packaging:** Docker Compose optional; for the GPU box, run vLLM + FastAPI directly. Save all work to `/workspace/shared` and download the codebase locally before June 14 (VFS is destroyed).

---

## 5. Repository structure

```
quorum/
├── README.md
├── backend/
│   ├── main.py                 # FastAPI app + endpoints
│   ├── orchestrator.py         # async fan-out to jurors + baseline
│   ├── jurors.py               # juror definitions (personas / model map)
│   ├── adjudicator.py          # aggregation logic
│   ├── inference.py            # vLLM client (and MOCK client)
│   ├── schemas.py              # pydantic contracts (Case, Verdict, Decision)
│   ├── config.py               # model list, council size, endpoints, flags
│   └── metrics.py              # tokens, latency, accuracy logging
├── eval/
│   ├── prepare_data.py         # load + label public dataset → cases.jsonl
│   ├── run_eval.py             # single-model vs council, writes results
│   └── data/                   # cases.jsonl, ground truth
├── bench/
│   └── amd_benchmark.py        # concurrent vs sequential juror throughput
├── frontend/                   # Next.js dashboard
│   └── app/page.tsx
├── scripts/
│   ├── serve_vllm.sh           # launch vLLM server(s) on ROCm
│   └── smoke_test.py           # end-to-end sanity check
└── docs/
    ├── demo_script.md
    └── slides_outline.md
```

---

## 6. Data contracts (build these FIRST — everything depends on them)

`schemas.py`:

```python
# Case: one record to be decided
class Case(BaseModel):
    case_id: str
    profile: dict          # structured fields (name, country, account age, etc.)
    narrative: str         # free-text description / activity summary
    # ground_truth is held out of what jurors see; used only by eval
    ground_truth: Optional[Literal["APPROVE", "REJECT"]] = None

# Verdict: one juror's output (STRICT JSON, no prose around it)
class Verdict(BaseModel):
    juror_id: str
    decision: Literal["APPROVE", "REJECT"]
    confidence: float          # 0.0 - 1.0
    rationale: str             # <= 3 sentences
    flags: list[str]           # risk signals cited
    tokens_used: int
    latency_ms: float

# Decision: adjudicator output (the auditable artifact)
class Decision(BaseModel):
    case_id: str
    final_decision: Literal["APPROVE", "REJECT", "ESCALATE"]
    panel_confidence: float
    agreement_ratio: float     # fraction of jurors agreeing with majority
    dissent_report: list[Verdict]   # the minority opinions, verbatim
    all_verdicts: list[Verdict]
    rationale_summary: str
```

**Acceptance:** schemas import cleanly; a hand-written example `Case`, three `Verdict`s, and one `Decision` validate.

---

## 7. Component specs

### 7.1 Inference client (`inference.py`)
- `class InferenceClient` with `async def complete(model, system, user, temperature, seed) -> (text, tokens, latency_ms)`.
- Two implementations behind the same interface:
  - `VLLMClient` → calls the vLLM OpenAI-compatible endpoint.
  - `MockClient` → returns canned/randomised structured verdicts **without any GPU** (used for all of Phase 0/2 dev).
- A `config.USE_MOCK` flag switches between them.

**Acceptance:** with `USE_MOCK=True`, the whole pipeline runs end-to-end on a laptop with no GPU.

### 7.2 Jurors (`jurors.py`)
- Define the council: list of `(juror_id, model, system_prompt, temperature)`.
- **Juror system-prompt contract** (each juror): "You are {persona}. Review the case. Output ONLY valid JSON matching this schema: {Verdict fields}. Do not invent facts not present in the case. If evidence is insufficient, lower your confidence."
- Personas (Option A): `compliance_officer` (strict, rule-focused), `risk_analyst` (pattern/behaviour-focused), `devils_advocate` (argues the opposite of the obvious read).
- Output must be parsed strictly; strip markdown fences; retry once on parse failure, then mark juror `ABSTAIN`.

**Acceptance:** each juror returns a schema-valid `Verdict` for a sample case (mock and real).

### 7.3 Orchestrator (`orchestrator.py`)
- `async def deliberate(case) -> Decision`: fan out to all jurors **concurrently** (`asyncio.gather`) + run the single-model **baseline** in parallel.
- Collect verdicts, hand to adjudicator, return `Decision`.
- Time the whole thing; record per-juror and total tokens/latency.

**Acceptance:** concurrent deliberation is measurably faster than sequential (log both).

### 7.4 Adjudicator (`adjudicator.py`)
Rules (deterministic first; an LLM "chief judge" is an optional Phase 3 upgrade):
- Majority vote → tentative decision.
- `agreement_ratio = majority_count / total_jurors`.
- `panel_confidence = mean(confidence of majority jurors) * agreement_ratio`.
- **Routing:** if `agreement_ratio < 0.66` **or** `panel_confidence < 0.6` → `ESCALATE` (this is the human-in-the-loop value). Otherwise the majority decision.
- `dissent_report` = all minority verdicts, verbatim, for the audit trail.
- `rationale_summary` = concatenated/condensed majority rationales.

**Acceptance:** given mixed verdicts, low agreement correctly produces `ESCALATE`; clear agreement produces a confident decision.

### 7.5 Metrics (`metrics.py`)
Log per decision: tokens (per juror + total), latency (p50/p95 across a run), accuracy vs ground truth, contradiction-catch events. Write JSONL + a summary table.

---

## 8. Data plan (`eval/prepare_data.py`)

Requirement: **public datasets only.** Pick ONE primary; verify availability in the first 30 min.

Candidates (in order of preference for an LLM jury that must *reason over text*):
1. **CFPB Consumer Complaint Database** (public, text-rich) — reframe as risk/escalation decisions; derive labels from `Company response` / dispute flags.
2. **PaySim** or **"Synthetic Financial Datasets for Fraud Detection"** (Kaggle) — tabular fraud with clear `isFraud` labels; generate a short narrative per row so jurors have text to reason over.
3. **IEEE-CIS Fraud Detection** (Kaggle) — large labeled fraud set.
4. **Fallback:** synthesise ~150 realistic labeled KYC cases (structured profile + narrative + APPROVE/REJECT) grounded on public risk heuristics and public sanctions/PEP list patterns. Document the synthesis method (legitimate since labels are needed and data must be non-proprietary).

Output: `cases.jsonl` of `Case` records, ~100–200 cases, balanced labels, **ground_truth held separate** from juror inputs.

**Acceptance:** `cases.jsonl` exists, loads into `Case` objects, label distribution printed.

---

## 9. Evaluation harness (`eval/run_eval.py`) — this produces Slide 4

For every case, run **(a)** single-model baseline and **(b)** Quorum council. Compute:
- **Accuracy / precision / recall** — baseline vs council.
- **Contradiction-catch rate** — count of cases where the baseline was confidently wrong (high confidence, wrong label) and the council corrected it. *This is the headline number.*
- **Escalation quality** — of cases routed to `ESCALATE`, what fraction were genuinely ambiguous / mislabeled-prone.
- **Cost:** tokens per decision (baseline vs council), p50/p95 latency.

Write `eval/results.json` + a printed markdown table.

**Acceptance:** one command runs the full eval and prints the comparison table.

---

## 10. AMD benchmark (`bench/amd_benchmark.py`) — this produces the AMD chart

Measure and chart:
- **Concurrent vs sequential** juror execution: throughput (decisions/min) and p95 latency for a 3-juror panel run concurrently vs one-after-another.
- **VRAM utilisation** while the full council is co-located (capture `rocm-smi` output).
- If Option B (multi-model): show 2–3 distinct models served simultaneously on one GPU.

Narrative for the slide: *"One AMD Instinct GPU runs the entire jury in parallel — Nx the throughput of sequential evaluation, at X% VRAM."*

**Acceptance:** a chart + numbers saved to `bench/results/`.

---

## 11. Dashboard (`frontend/`) — this produces the demo

Single page, three zones:
1. **Case input** — pick a case from a dropdown (or paste one) → "Deliberate".
2. **Live jury view** — each juror card streams in: verdict, confidence bar, rationale, flags. Disagreement is visually obvious (red vs green cards).
3. **Verdict panel** — final decision badge (`APPROVE`/`REJECT`/`ESCALATE`), panel confidence, dissent report, and a **"Single model said: ___"** comparison line.

Include a **"Demo case"** button that loads the planted fraudulent case where the single model says APPROVE and the jury catches it.

**Acceptance:** non-technical viewer watches a case get decided and immediately understands what happened.

---

## 12. Phase plan (respects the 4hr/24hr GPU limit)

> **GPU discipline:** everything that does not strictly need a GPU is built/tested with `USE_MOCK=True` on a laptop. GPU windows are reserved only for real inference, eval, and benchmarks.

### Phase 0 — Local scaffold (NO GPU)
- [ ] Repo structure + README.
- [ ] `schemas.py` contracts (Section 6).
- [ ] `MockClient` + `InferenceClient` interface.
- [ ] Jurors, orchestrator, adjudicator working end-to-end on mock.
- [ ] `smoke_test.py` passes on mock.
- [ ] Dashboard renders a full deliberation from the mock backend.
- **Done when:** you can demo the *entire flow* on your laptop with fake inference.

### Phase 1 — First GPU window (real inference)
- [ ] Confirm allocated GPU + VRAM (`rocm-smi`); decide Option A vs B.
- [ ] `serve_vllm.sh` launches vLLM with the primary model on ROCm.
- [ ] Swap `USE_MOCK=False`; validate jurors return schema-valid JSON from the real model.
- [ ] Run eval on a **small slice** (~20 cases) to confirm the pipeline + capture first metrics.
- [ ] Save everything to `/workspace/shared`; **download codebase locally**.
- **Done when:** real model produces real decisions; small eval table exists.

### Phase 2 — Local polish (NO GPU)
- [ ] Full eval harness + contradiction-catch logic.
- [ ] Plant + verify the demo case (single model wrong → jury right).
- [ ] Dashboard polish: dissent visualisation, side-by-side comparison.
- [ ] Draft deck + demo script.
- **Done when:** demo is dramatic and the eval logic is final.

### Phase 3 — Second GPU window (scale + benchmark)
- [ ] Upgrade to multi-model council (Option B) if VRAM allows.
- [ ] Full eval run over all cases → final numbers.
- [ ] AMD concurrency benchmark + VRAM capture → final chart.
- [ ] Re-download codebase + results locally.
- **Done when:** final accuracy table + AMD chart are captured.

### Phase 4 — Package & submit (NO GPU)
- [ ] Finalise 5-slide deck (Section 13).
- [ ] Record demo (Clipchamp / Google Vids, or screenshots → PDF).
- [ ] Clean README with run instructions + dataset/code links.
- [ ] Submit on Ultimatix Prime Events: code files + deck + demo.
- **Done when:** submission checklist (Section 15) is fully ticked.

---

## 13. Deck outline (3–5 slides, required structure)

1. **Basic Information** — team/individual + roles; use case (Agentic KYC / AGENTS_002); one-line description + the tagline.
2. **Problem & Context** — single-LLM decisions hallucinate and aren't auditable; stakeholders = compliance/risk teams; why it matters (regulatory, financial); mapped challenge = AGENTS_002.
3. **Solution Overview** — the jury+adjudicator architecture diagram; AI approach (multi-agent consensus, RAG-free reasoning); frameworks (vLLM, FastAPI, Next.js); what was built during the hackathon.
4. **Model Insights** — models used; dataset + source; tokens per decision; end-to-end latency (p50/p95); **GPU + VRAM usage**; **the AMD concurrency chart**; **baseline vs council accuracy + contradiction-catch rate**.
5. **Impact & Demo Summary** — expected impact (auditable, fewer false approvals); key differentiator (consensus-as-verification on one AMD GPU); demo flow (what the jury should notice — the caught hallucination); future extension (LLM chief-judge, more jurors, domain fine-tuned jurors).

(Template downloadable from the Prime Hub page — use it.)

---

## 14. Demo script (`docs/demo_script.md`)

1. Open dashboard. "Here's a customer onboarding case."
2. Run a single model → it says **APPROVE** with high confidence.
3. Run the Quorum jury on the same case → jurors disagree; one flags a risk signal; adjudicator returns **REJECT / ESCALATE** with the dissent report.
4. "The single model would have approved a fraudulent customer. The jury caught it — and produced an audit trail."
5. Cut to Slide 4: accuracy lift + contradiction-catch rate + the AMD throughput chart. "And the whole jury runs on one AMD Instinct GPU, in parallel."

---

## 15. Definition of done / submission checklist

- [ ] Working backend (jurors + adjudicator) — real inference on AMD.
- [ ] Eval results: baseline vs council, with contradiction-catch number.
- [ ] AMD concurrency benchmark + VRAM chart.
- [ ] Dashboard with the live side-by-side demo.
- [ ] 5-slide deck following the required structure.
- [ ] Demo recording.
- [ ] Code downloaded locally (VFS destroyed June 14) + links to code + public dataset.
- [ ] Clearly stated what was built during the hackathon vs reused (disclose any prior code).
- [ ] Submitted on Ultimatix Prime Events.

---

## 16. Risk & contingency

- **GPU unavailable / window lost:** the entire system runs on `MockClient`; you can still build, demo the flow, and only need *one* short GPU window for real numbers. No training = low variance.
- **JSON parse failures from jurors:** strict parse + one retry + `ABSTAIN` fallback; never let a malformed verdict crash a decision.
- **VRAM too small for Option B:** fall back to Option A (persona jurors on one model) — the consensus story and benchmark still hold.
- **Weak dataset labels:** fall back to the synthesised labeled case set (Section 8, candidate 4), documented.

---

## 17. First commands to build

1. "Scaffold the repo per Section 5 and implement `schemas.py` from Section 6."
2. "Implement `inference.py` with `MockClient` + `VLLMClient` behind one interface, `USE_MOCK` flag."
3. "Implement `jurors.py`, `orchestrator.py` (async fan-out), and `adjudicator.py` per Section 7. Make `smoke_test.py` pass on mock."
4. "Build the Next.js dashboard (Section 11) against the mock backend."
5. → Then take it to the GPU for Phase 1.

**Golden rule:** never commit-only locally — push to GitHub after every working change.
