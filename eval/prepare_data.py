"""Synthesize a balanced, labeled KYC case set -> eval/data/cases.jsonl.

Section 8 candidate 4 (fallback, fully public/non-proprietary): we generate
~150 realistic KYC onboarding cases from public risk heuristics (sanctions/PEP
patterns, source-of-funds gaps, document mismatches, structuring). Labels are
APPROVE/REJECT and held in ground_truth, separate from juror inputs.

One case is PLANTED for the demo: it looks clean on the surface (so a naive
single model approves) but carries a buried REJECT-worthy signal the jury catches.
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "cases.jsonl"

COUNTRIES_LOW = ["Germany", "Canada", "Japan", "Australia", "Netherlands"]
COUNTRIES_HIGH = ["Iran", "North Korea", "Syria", "a high-risk jurisdiction"]
NAMES = ["A. Okafor", "L. Petrov", "M. Haddad", "S. Chen", "R. Gomez", "K. Novak",
         "T. Yilmaz", "D. Costa", "E. Larsson", "N. Reddy"]

# (narrative fragment, is_risk_signal)
RISK_FRAGMENTS = [
    "appears on a sanction screening hit",
    "funds routed through a shell company",
    "name mismatch between ID and bank records",
    "no source of funds provided for large deposits",
    "transaction pattern consistent with structuring",
    "flagged as a PEP with undisclosed relationships",
    "registered in a high-risk jurisdiction",
    "submitted a forged utility bill",
    "uses an anonymous prepaid contact method",
]
CLEAN_FRAGMENTS = [
    "stable salaried income with consistent payroll deposits",
    "documents verified and consistent across sources",
    "long-standing banking relationship with no disputes",
    "transparent, well-documented source of funds",
    "low-value, regular transactions matching stated profile",
]


def _profile(rng, risky):
    return {
        "name": rng.choice(NAMES),
        "country": rng.choice(COUNTRIES_HIGH if risky else COUNTRIES_LOW),
        "account_age_months": rng.randint(0, 6) if risky else rng.randint(12, 120),
        "declared_income_usd": rng.choice([45000, 60000, 80000, 120000]),
    }


def synthesize(n=150, seed=42):
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        risky = i % 2 == 0  # balanced labels
        profile = _profile(rng, risky)
        if risky:
            frags = rng.sample(RISK_FRAGMENTS, k=rng.randint(2, 3))
            frags += rng.sample(CLEAN_FRAGMENTS, k=1)
            label = "REJECT"
        else:
            frags = rng.sample(CLEAN_FRAGMENTS, k=rng.randint(2, 3))
            label = "APPROVE"
        rng.shuffle(frags)
        narrative = (
            f"Applicant {profile['name']} from {profile['country']} "
            f"({profile['account_age_months']} mo history). "
            + " The applicant ".join([""] + frags).strip()
            + "."
        )
        cases.append({
            "case_id": f"CASE-{i:03d}",
            "profile": profile,
            "narrative": narrative,
            "ground_truth": label,
        })

    # Planted demo case: surface-clean wording, buried sanction hit -> REJECT.
    cases.insert(0, {
        "case_id": "DEMO-FRAUD",
        "profile": {
            "name": "V. Castellano",
            "country": "Netherlands",
            "account_age_months": 36,
            "declared_income_usd": 95000,
        },
        "narrative": (
            "Applicant V. Castellano presents a polished, professional profile "
            "with a long banking history and stable income. Onboarding looks "
            "routine. A back-office note buried in the file shows the applicant "
            "appears on a sanction screening hit and funds were routed through "
            "a shell company, with no source of funds provided for large deposits."
        ),
        "ground_truth": "REJECT",
    })
    return cases


def main():
    cases = synthesize()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    labels = [c["ground_truth"] for c in cases]
    dist = {lab: labels.count(lab) for lab in set(labels)}
    print(f"Wrote {len(cases)} cases to {OUT}")
    print(f"Label distribution: {dist}")


if __name__ == "__main__":
    main()
