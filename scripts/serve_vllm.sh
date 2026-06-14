#!/usr/bin/env bash
# Launch a vLLM OpenAI-compatible server on AMD ROCm (Phase 1).
# Option A: one server, one strong model; jurors differ by persona.
set -euo pipefail

MODEL="${PRIMARY_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
PORT="${VLLM_PORT:-8001}"
GPU_UTIL="${GPU_MEMORY_UTILIZATION:-0.85}"
MAX_LEN="${MAX_MODEL_LEN:-8192}"

# Preflight: confirm a GPU is visible before pulling weights.
if command -v rocm-smi >/dev/null 2>&1; then
  echo "== rocm-smi =="
  rocm-smi --showproductname --showmeminfo vram || true
  echo "=============="
else
  echo "WARN: rocm-smi not found — are you on the AMD GPU box?"
fi

echo "Serving $MODEL on :$PORT (ROCm, gpu-util=$GPU_UTIL, max-len=$MAX_LEN)"
python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --port "$PORT" \
  --dtype auto \
  --max-model-len "$MAX_LEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --trust-remote-code

# Then, in a second shell, point the backend at it:
#   export USE_MOCK=False
#   export VLLM_BASE_URL=http://localhost:8001/v1
#   export PRIMARY_MODEL=$MODEL
#   python scripts/smoke_test.py     # validate real JSON verdicts
#   python eval/run_eval.py          # real numbers
#
# Option B (multi-model, if VRAM allows): run this script N times with a
# different PRIMARY_MODEL and VLLM_PORT each, then map jurors to ports in
# backend/jurors.py. See docs/gpu_runbook.md.
