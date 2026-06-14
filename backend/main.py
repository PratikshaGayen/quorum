"""FastAPI app: orchestrator endpoints for the dashboard.

GET  /api/cases            -> list of demo cases (no ground_truth leaked)
POST /api/deliberate       -> run the jury on a case, return a Decision
GET  /api/health           -> mock/real + council size
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .jurors import COUNCIL
from .orchestrator import deliberate
from .schemas import Case, Decision

CASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "data" / "cases.jsonl"

app = FastAPI(title="Quorum", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_cases() -> dict[str, Case]:
    if not CASES_PATH.exists():
        return {}
    cases: dict[str, Case] = {}
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = Case(**json.loads(line))
            cases[c.case_id] = c
    return cases


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock": config.USE_MOCK,
        "model": config.PRIMARY_MODEL,
        "council_size": len(COUNCIL),
        "cases_loaded": len(_load_cases()),
    }


@app.get("/api/cases")
def list_cases() -> list[dict]:
    # Strip ground_truth so the UI never reveals the answer.
    out = []
    for c in _load_cases().values():
        out.append({"case_id": c.case_id, "profile": c.profile, "narrative": c.narrative})
    return out


@app.post("/api/deliberate", response_model=Decision)
async def deliberate_endpoint(case: Case) -> Decision:
    if not case.narrative and not case.profile:
        raise HTTPException(status_code=400, detail="case needs profile or narrative")
    case.ground_truth = None  # never let jurors see the label
    return await deliberate(case)
