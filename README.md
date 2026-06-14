# Quorum — a verifiable decision engine

> We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom.

Instead of one LLM making an approve/reject call, Quorum runs a **jury of diverse LLM personas in parallel** on a single GPU. Each juror returns a structured verdict (decision + confidence + rationale + risk flags); an **adjudicator** combines them into a final `APPROVE` / `REJECT` / `ESCALATE` with a panel-confidence score and a verbatim **dissent report**. Every decision ships with an audit trail.

**Use case:** Agentic KYC / fraud onboarding review (AGENTS_002).

## Architecture

```
Case (JSON) → FastAPI orchestrator → async fan-out to N jurors + 1 baseline
                                    → adjudicator (majority + confidence + routing)
                                    → Decision (+ dissent) → Next.js dashboard
```

Jurors (Option A): one base model, distinct personas — `compliance_officer`, `risk_analyst`, `devils_advocate` — at varied temperatures. A lenient `baseline_single_model` represents a naive solo LLM for the side-by-side demo.

## Run it locally (no GPU — mock inference)

```bash
pip install -r requirements.txt

# 1. synthesize the labeled case set (incl. the planted DEMO-FRAUD case)
python eval/prepare_data.py

# 2. sanity check the whole pipeline
python scripts/smoke_test.py

# 3. baseline vs council comparison (Slide 4 numbers)
python eval/run_eval.py

# 4. concurrent vs sequential throughput (AMD chart)
python bench/amd_benchmark.py

# 5. backend + dashboard
python -m uvicorn backend.main:app --port 8000
cd frontend && npm install && npm run dev   # http://localhost:3000
```

`USE_MOCK=True` (default) runs everything with deterministic fake inference. Click **Demo case (planted fraud)** in the dashboard: the single model approves, the jury catches it.

## Run on the AMD GPU box (Phase 1)

```bash
bash scripts/serve_vllm.sh                 # vLLM on ROCm, :8001
export USE_MOCK=False
export VLLM_BASE_URL=http://localhost:8001/v1
python scripts/smoke_test.py               # validate real JSON verdicts
python eval/run_eval.py --limit 20         # small slice first (cheap insurance)
python eval/run_eval.py                     # full real accuracy / contradiction-catch
python bench/amd_benchmark.py               # captures rocm-smi VRAM
```

Full step-by-step with checks, troubleshooting, and the Option B (multi-model)
path: **[`docs/gpu_runbook.md`](docs/gpu_runbook.md)**.

## Layout

| Path | What |
|---|---|
| `backend/schemas.py` | `Case` / `Verdict` / `Decision` contracts |
| `backend/inference.py` | `MockClient` + `VLLMClient` behind one interface |
| `backend/jurors.py` | council personas + strict JSON parse / ABSTAIN fallback |
| `backend/orchestrator.py` | async fan-out (`deliberate`) + sequential variant for bench |
| `backend/adjudicator.py` | majority vote, panel confidence, ESCALATE routing |
| `backend/main.py` | FastAPI endpoints for the dashboard |
| `eval/` | data synthesis + baseline-vs-council eval harness |
| `bench/` | concurrent-vs-sequential throughput + VRAM capture |
| `frontend/` | Next.js single-page deliberation dashboard |

## Dataset

~150 balanced, labeled KYC/onboarding cases are **synthesized** by
`eval/prepare_data.py` (spec Section 8, candidate 4) from public risk heuristics
and sanctions/PEP patterns — chosen so the data is non-proprietary and ground
truth is available. No customer data is used. The synthesis method lives in that
script; `cases.jsonl` holds the output, with `ground_truth` held separate from
what jurors see.

## What was built during the hackathon

All code in this repository was written for this hackathon — backend
(orchestrator, jurors, adjudicator, inference clients, schemas), eval + benchmark
harnesses, the synthesized dataset, and the Next.js dashboard. No prior/proprietary
code was reused. Third-party dependencies are standard OSS (FastAPI, pydantic,
httpx, vLLM, Next.js, Tailwind); models are open-weight (Qwen2.5-7B-Instruct, and
optionally Llama-3.1-8B / Mistral-7B for Option B).

## Status

Phase 0 (local scaffold on mock) complete and verified: smoke test passes, eval +
bench produce results, dashboard renders a full deliberation. GPU phases (real
inference, final numbers, multi-model Option B) are pending a GPU window — see
`docs/gpu_runbook.md`. Numbers currently in `eval/results.json` /
`bench/results/` are deterministic **mock** placeholders; the GPU run overwrites
them.
