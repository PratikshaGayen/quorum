# Quorum — explained simply

## The one-line version

When a bank decides whether to let a new customer open an account, **Quorum doesn't ask one AI — it asks a small jury of AIs, lets them argue, and gives you a verdict *with the reasons written down*.**

---

## The problem (in plain words)

Banks have to check every new customer for fraud, money laundering, sanctions, etc. This is called **KYC** ("Know Your Customer"). Today people are starting to use a single AI to read each case and say "approve" or "reject."

That's risky, because a single AI:
- **Sounds confident even when it's wrong.**
- **Makes things up** sometimes (hallucinates).
- **Doesn't show its work** — so if a regulator later asks "why did you approve this fraudster?", there's no good answer.

For a bank, a wrong "approve" can let a criminal in; a wrong "reject" loses a real customer. Both get you fined. So "one confident AI with no paper trail" is not good enough.

---

## Our idea: a courtroom instead of one judge

Think of how a courtroom works: you don't trust **one** person's gut feeling for a serious decision. You get **several people with different viewpoints**, let them disagree, and record the reasoning.

Quorum does exactly that for KYC. For each customer case, it runs **three AI "jurors," each with a different personality:**

- 🧑‍⚖️ **The Compliance Officer** — strict, goes by the rulebook.
- 🔍 **The Risk Analyst** — looks for weird patterns in the money and behavior.
- 😈 **The Devil's Advocate** — deliberately argues the opposite, to surface things others missed.

Each juror reads the case and gives a verdict **plus the reasons**. Then a final step, the **Adjudicator**, counts the votes:
- If they mostly agree → that's the decision (Approve or Reject).
- If they **disagree**, it doesn't guess — it says **"Escalate"** and sends the case to a human, *with a record of who disagreed and why.*

The clever part: all three jurors run **at the same time on a single AMD graphics chip (GPU)**, so it's fast and cheap — like having a whole panel that answers in about a second.

---

## Why this is better (we measured it)

We tested a single AI vs. our jury on **151 made-up customer cases** (no real customer data — we created them so we'd know the right answers).

| What we checked | One AI alone | Quorum's jury |
|---|---|---|
| How often it got the case right | **70%** | **98%** |
| How many of the *bad actors* it caught | **43%** (missed more than half!) | **96%** |
| How often it wrongly blocked a *good* customer | never | never |

The headline: in **43 of the 151 cases, the single AI was confidently wrong — and the jury caught the mistake.**

It costs a bit more (the jury "thinks out loud," so it uses more computing), but for a decision that can get a bank fined, that's a very cheap insurance.

---

## What makes it special

1. **Trust through disagreement.** It's safer *because* the AIs argue, not because we used a bigger/smarter AI.
2. **Always shows its work.** Every decision comes with the reasons and any dissent — exactly what an auditor or regulator wants.
3. **Knows when to ask a human.** Genuinely unclear cases get escalated (about 1 in 5), instead of a confident guess.
4. **Runs on a single AMD GPU**, all jurors in parallel.

---

## The tagline

> *We don't make AI smarter — we make its decisions trustworthy and auditable, by turning one AMD Instinct GPU into a courtroom.*

---

## How the pieces fit (for the curious)

```
  Customer case
       │
       ▼
  ┌──────────────────────────────────────────────┐
  │  3 AI jurors think at the same time:         │
  │  Compliance Officer · Risk Analyst · Devil's │
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │  Adjudicator: counts votes →                 │
  │  APPROVE / REJECT / ESCALATE (+ the reasons) │
  └──────────────────────────────────────────────┘
```

- The AI model is **Qwen2.5-7B** (an open model), run with **vLLM** on an **AMD Instinct MI300X** GPU.
- The screen you'd demo is a simple **web dashboard** that shows the single AI's answer next to the jury's, so you can *see* the jury catch a mistake live.
