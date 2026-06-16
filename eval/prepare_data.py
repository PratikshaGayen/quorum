"""Synthesize a graded, labeled KYC case set -> eval/data/cases.jsonl.

Section 8 candidate 4 (fully public/non-proprietary). Cases are generated in
four difficulty bands so the eval can show what a *council* actually adds over a
single model:

  - clean     : genuinely fine            -> APPROVE  (baseline and council agree)
  - blatant   : explicit smoking-gun risk -> REJECT   (a solo model catches these too)
  - subtle    : risk is *implicit*        -> REJECT   (a lenient single read approves
                at face value; a skeptical, diverse panel catches it)
  - ambiguous : conflicting signals       -> REJECT   (the defensible call, but expected
                to split the panel -> ESCALATE to a human)

The whole design point: in the `subtle` and `ambiguous` bands the risk is never
named with trigger words ("sanction", "shell company", "structuring", "fraud").
It lives in the numbers and relationships and has to be *inferred* — which is
exactly where a single lenient model fails and a council earns its cost. Labels
live in `ground_truth`, separate from what jurors see.
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "cases.jsonl"

# Band sizes (plus one planted DEMO case). Tuned so labels are roughly balanced.
N_CLEAN = 70
N_BLATANT = 25
N_SUBTLE = 40
N_AMBIGUOUS = 15

LOW_RISK = ["Germany", "Canada", "Japan", "Australia", "Netherlands", "Sweden", "Singapore"]
HIGH_RISK = ["Iran", "North Korea", "Syria", "Myanmar", "a sanctioned jurisdiction"]
NAMES = ["A. Okafor", "L. Petrov", "M. Haddad", "S. Chen", "R. Gomez", "K. Novak",
         "T. Yilmaz", "D. Costa", "E. Larsson", "N. Reddy", "F. Bianchi", "J. Mwangi"]


def _profile(rng, *, country, age_lo, age_hi, income=None):
    return {
        "name": rng.choice(NAMES),
        "country": country,
        "account_age_months": rng.randint(age_lo, age_hi),
        "declared_income_usd": income if income is not None else rng.choice([45000, 60000, 80000, 120000]),
    }


# --- clean (APPROVE) ----------------------------------------------------------
CLEAN_LINES = [
    "Payroll deposits arrive on a regular monthly schedule and match the declared salary.",
    "Identity documents were verified against two independent sources with no discrepancies.",
    "A long, stable banking relationship with low-value transactions consistent with the stated profile.",
    "Source of funds is fully documented and transparent, with no adverse media.",
    "Account activity is modest and regular, in line with a salaried professional.",
]


def make_clean(rng):
    p = _profile(rng, country=rng.choice(LOW_RISK), age_lo=18, age_hi=120)
    lines = rng.sample(CLEAN_LINES, k=3)
    narrative = f"Applicant {p['name']} from {p['country']} ({p['account_age_months']} mo history). " + " ".join(lines)
    return p, narrative, "APPROVE"


# --- blatant (REJECT, explicitly stated) -------------------------------------
BLATANT_LINES = [
    "appears on a sanction screening hit",
    "submitted a forged utility bill",
    "funds were routed through a shell company with no source of funds provided",
    "ID details do not match the bank records and a watchlist alert was raised",
    "flagged as a PEP with undisclosed relationships and adverse media",
]


def make_blatant(rng):
    p = _profile(rng, country=rng.choice(HIGH_RISK), age_lo=0, age_hi=6)
    risk = rng.sample(BLATANT_LINES, k=rng.randint(1, 2))
    narrative = (
        f"Applicant {p['name']} from {p['country']} ({p['account_age_months']} mo history). "
        f"The applicant " + ", and ".join(risk) + "."
    )
    return p, narrative, "REJECT"


# --- subtle (REJECT, risk implicit; a lenient read approves) ------------------
def _subtle_income_mismatch(rng):
    income = rng.choice([48000, 55000, 62000])
    deposits = rng.choice([950000, 1400000, 2200000])
    months = rng.randint(3, 6)
    return income, (
        f"Over the past {months} months the account received aggregate deposits of "
        f"${deposits:,}, which the onboarding note characterises as 'healthy account "
        f"activity'. Paperwork is otherwise in order."
    )


def _subtle_threshold_deposits(rng):
    n = rng.randint(8, 14)
    amt = rng.choice([9200, 9400, 9600, 9800])
    return None, (
        f"The account shows {n} separate cash deposits of ${amt:,} each over a nine-day "
        f"period, described by the relationship manager as 'regular deposits'."
    )


def _subtle_passthrough(rng):
    return None, (
        "The account regularly receives six-figure transfers from newly registered "
        "counterparties and forwards them within a day, which the file describes as "
        "'consistent with the client's consulting business'."
    )


def _subtle_geo(rng):
    home = rng.choice(LOW_RISK)
    elsewhere = rng.choice(HIGH_RISK)
    return None, (
        f"The applicant lists a residential address in {home}, though all account logins "
        f"and incoming wires originate from {elsewhere}; the file notes 'frequent business travel'."
    )


def _subtle_ownership(rng):
    return None, (
        "The business is owned through a holding company whose ultimate beneficial owner "
        "is listed as 'under review', which the onboarding analyst marked as a 'standard "
        "corporate structure'."
    )


SUBTLE_GENERATORS = [
    _subtle_income_mismatch, _subtle_threshold_deposits, _subtle_passthrough,
    _subtle_geo, _subtle_ownership,
]


def make_subtle(rng):
    # Surface-clean: low-risk country, established account, professional framing.
    income_hint, line = rng.choice(SUBTLE_GENERATORS)(rng)
    p = _profile(rng, country=rng.choice(LOW_RISK), age_lo=12, age_hi=72, income=income_hint)
    narrative = (
        f"Applicant {p['name']} presents a polished, professional profile from "
        f"{p['country']} with a {p['account_age_months']}-month history; onboarding "
        f"looks routine. " + line
    )
    return p, narrative, "REJECT"


# --- ambiguous (REJECT defensible, but a genuine judgement call -> ESCALATE) --
AMBIGUOUS_LINES = [
    ("resides in {high}, a higher-risk jurisdiction, but provides a fully documented, "
     "independently audited source of funds and a long, transparent history"),
    ("had one historical adverse-media mention that was later retracted, but operates "
     "in a cash-intensive industry with otherwise consistent records"),
    ("uses a complex but lawful multi-entity corporate structure with all beneficial "
     "owners disclosed, alongside one transfer to a moderately high-risk counterparty"),
]


def make_ambiguous(rng):
    p = _profile(rng, country=rng.choice(LOW_RISK), age_lo=24, age_hi=120)
    line = rng.choice(AMBIGUOUS_LINES).format(high=rng.choice(HIGH_RISK))
    narrative = f"Applicant {p['name']} ({p['account_age_months']} mo history) {line}."
    return p, narrative, "REJECT"


def synthesize(seed=42):
    rng = random.Random(seed)
    rows = []

    def add(case_id, builder):
        p, narrative, label = builder(rng)
        rows.append({"case_id": case_id, "profile": p, "narrative": narrative, "ground_truth": label})

    for i in range(N_CLEAN):
        add(f"CLEAN-{i:03d}", make_clean)
    for i in range(N_BLATANT):
        add(f"BLAT-{i:03d}", make_blatant)
    for i in range(N_SUBTLE):
        add(f"SUBTLE-{i:03d}", make_subtle)
    for i in range(N_AMBIGUOUS):
        add(f"AMBIG-{i:03d}", make_ambiguous)

    rng.shuffle(rows)

    # Planted demo case: surface-clean wording, buried pass-through/layering -> REJECT.
    rows.insert(0, {
        "case_id": "DEMO-FRAUD",
        "profile": {"name": "V. Castellano", "country": "Netherlands",
                    "account_age_months": 36, "declared_income_usd": 95000},
        "narrative": (
            "Applicant V. Castellano presents a polished profile: a 36-month banking "
            "history, professional references, and a declared income of $95,000. "
            "Onboarding looks routine. The file notes that the account regularly "
            "receives six-figure transfers from newly registered counterparties and "
            "forwards them within a day, which the relationship manager describes as "
            "'consistent with the client's consulting business'."
        ),
        "ground_truth": "REJECT",
    })
    return rows


def main():
    cases = synthesize()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    labels = [c["ground_truth"] for c in cases]
    dist = {lab: labels.count(lab) for lab in sorted(set(labels))}
    print(f"Wrote {len(cases)} cases to {OUT}")
    print(f"Label distribution: {dist}")


if __name__ == "__main__":
    main()
