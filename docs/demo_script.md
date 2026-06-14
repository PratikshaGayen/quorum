# Quorum — demo script

1. **Open the dashboard.** "Here's a customer onboarding case for a KYC review."
2. **Show the planted case.** Click **Demo case (planted fraud)** — `DEMO-FRAUD`. The narrative reads clean and professional on the surface.
3. **The single model.** Point at the "Single model said" panel: **APPROVE**, high confidence. "A solo LLM waves this through."
4. **The jury.** The three juror cards come back **REJECT** — each cites the buried risk flags (sanction hit, shell company, no source of funds). Disagreement with the baseline is visually obvious (red vs green).
5. **The verdict.** Adjudicator returns **REJECT / ESCALATE** with panel confidence and the **dissent report** — the audit trail. "The single model would have approved a fraudulent customer. The jury caught it, and produced a record of why."
6. **Cut to Slide 4.** Accuracy lift, **contradiction-catch rate**, and the **AMD throughput chart**. "And the whole jury runs on one AMD Instinct GPU, in parallel — Nx the throughput of running the models one at a time."
