"""Central config: mock flag, endpoints, council size, routing thresholds.

Everything tunable lives here so the GPU phase only touches env vars.
"""

import os


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


# Switch the whole pipeline between MockClient (no GPU) and VLLMClient (real).
USE_MOCK = _env_bool("USE_MOCK", True)

# vLLM OpenAI-compatible endpoint (Option A: one server, one model).
# Defaults to :8001 so it never collides with the FastAPI backend on :8000.
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")  # vLLM ignores the value
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "Qwen/Qwen2.5-7B-Instruct")

# Adjudicator routing thresholds (Section 7.4).
ESCALATE_AGREEMENT_BELOW = 0.66
ESCALATE_CONFIDENCE_BELOW = 0.60

# Per-juror request budget.
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
PARSE_RETRIES = 1
