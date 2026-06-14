# Quorum — GPU window runbook (Phases 1 & 3)

GPU time is the scarce resource (4hr/24hr limit). Everything below assumes the
laptop work is already done and verified on mock. Goal: get **real numbers** out
fast, save them, and download before the VFS is destroyed.

Run the steps top to bottom. Each has a check — don't proceed until it passes.

---

## 0. Before the window opens (do on the laptop)

- [ ] Confirm mock pipeline is green: `python scripts/smoke_test.py` → `SMOKE TEST PASSED`.
- [ ] Have this repo ready to `git clone` / `scp` onto the GPU box.
- [ ] Know your model: default is `Qwen/Qwen2.5-7B-Instruct` (Option A).

---

## 1. Land the code + confirm the GPU

```bash
cd /workspace/shared            # persistent-ish; still download locally after
git clone <your-repo-url> quorum && cd quorum   # or scp the folder
pip install -r requirements.txt
pip install vllm                # ROCm build per the handbook env

rocm-smi --showproductname --showmeminfo vram
```

**Check:** `rocm-smi` lists the Instinct card + total VRAM. Note the VRAM number —
it goes on Slide 4 and decides Option A vs B (≥80GB free → Option B is feasible).

---

## 2. Serve the model (Option A)

```bash
bash scripts/serve_vllm.sh      # serves Qwen2.5-7B on :8001, prints rocm-smi
```

Wait for `Application startup complete` / the Uvicorn line from vLLM.

**Check (second shell):**
```bash
curl -s http://localhost:8001/v1/models | python -m json.tool
```
returns the model id. If it hangs, the weights are still downloading — watch the
first shell.

---

## 3. Point the backend at the real server

```bash
export USE_MOCK=False
export VLLM_BASE_URL=http://localhost:8001/v1
export PRIMARY_MODEL=Qwen/Qwen2.5-7B-Instruct
```

**Check — real JSON verdicts end to end:**
```bash
python scripts/smoke_test.py
```
Expect the planted `DEMO-FRAUD` case to come back **REJECT** from the jury vs
**APPROVE** from the baseline. If a juror shows `ABSTAIN` with `parse_failure`,
the model isn't returning clean JSON — see Troubleshooting.

---

## 4. Small eval slice first (cheap insurance)

Don't burn the window on a full 151-case run before the pipeline is proven.

```bash
python eval/run_eval.py --limit 20      # first 20 cases only
```

**Check:** `eval/results.json` updates with real (non-mock) accuracy and a
non-zero `contradiction_catch_rate`. Eyeball that council accuracy ≥ baseline.

---

## 5. Full eval + AMD benchmark (the slide numbers)

```bash
python eval/run_eval.py                 # full 151 cases → results.json
python bench/amd_benchmark.py           # concurrent vs sequential + rocm-smi VRAM
```

**Check:** `eval/results.json` (accuracy, contradiction-catch, p50/p95 latency,
tokens/decision) and `bench/results/throughput.png` + `benchmark.json` (speedup,
VRAM %) all reflect the real run.

---

## 6. Save EVERYTHING before the window closes

```bash
cp eval/results.json bench/results/* /workspace/shared/quorum_results/
git add -A && git commit -m "Phase 1: real GPU results" && git push   # if remote set
```
Then **download `eval/results.json`, `bench/results/` locally** — the VFS is wiped.

**Check:** the result files are on your laptop, openable, with real numbers.

---

## Phase 3 — Option B (multi-model), only if VRAM ≥ ~80GB free

Stronger "many models, one AMD GPU" story. **Requires a small code change** —
right now every juror calls `config.PRIMARY_MODEL` through one base URL
(`backend/jurors.py:run_juror`). To do Option B:

1. Serve 2–3 models on different ports:
   ```bash
   PRIMARY_MODEL=Qwen/Qwen2.5-7B-Instruct       VLLM_PORT=8001 bash scripts/serve_vllm.sh &
   PRIMARY_MODEL=meta-llama/Llama-3.1-8B-Instruct VLLM_PORT=8002 bash scripts/serve_vllm.sh &
   PRIMARY_MODEL=mistralai/Mistral-7B-Instruct-v0.3 VLLM_PORT=8003 bash scripts/serve_vllm.sh &
   ```
   Lower `GPU_MEMORY_UTILIZATION` (e.g. 0.30 each) so they co-locate.
2. Add `model` + `base_url` fields to the `Juror` dataclass and pass them through
   `run_juror` instead of the globals.
3. `rocm-smi` while all three serve → screenshot for the slide.

If VRAM is tight, **stay on Option A** — the consensus story and benchmark still
hold. Don't gamble the window chasing Option B.

---

## Troubleshooting

- **Jurors ABSTAIN / parse_failure:** model is wrapping JSON in prose. `_strip_fences`
  already grabs the outermost `{...}`; if still failing, lower temperature in
  `backend/jurors.py` or add `"Respond with JSON only."` emphasis. Qwen2.5-Instruct
  is reliable here.
- **OOM on startup:** drop `GPU_MEMORY_UTILIZATION` (0.7) and/or `MAX_MODEL_LEN` (4096).
- **vLLM not found:** you're not on the ROCm box / wrong env — `serve_vllm.sh` warns
  if `rocm-smi` is missing.
- **Backend can't reach vLLM:** confirm `VLLM_BASE_URL` port matches `VLLM_PORT`
  (default 8001), not the FastAPI port (8000).
