# Quorum — 5-slide deck outline

1. **Basic Information** — team/roles; use case Agentic KYC (AGENTS_002); one-liner + tagline: *"We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom."*
2. **Problem & Context** — single-LLM decisions hallucinate and aren't auditable; stakeholders = compliance/risk teams; regulatory + financial stakes; mapped challenge AGENTS_002.
3. **Solution Overview** — jury + adjudicator architecture diagram; multi-agent consensus (RAG-free reasoning); stack vLLM + FastAPI + Next.js; what was built during the hackathon.
4. **Model Insights** — models + dataset/source; tokens per decision; p50/p95 latency; **GPU + VRAM usage**; **AMD concurrency chart** (`bench/results/throughput.png`); **baseline vs council accuracy + contradiction-catch rate** (`eval/results.json`).
5. **Impact & Demo Summary** — auditable decisions, fewer false approvals; differentiator = consensus-as-verification on one AMD GPU; demo flow (the caught hallucination); future work = LLM chief-judge, more jurors, multi-model Option B, domain-tuned jurors.

> Fill slide 4 with real numbers from the GPU run. Mock placeholders are in `eval/results.json` / `bench/results/benchmark.json`.
