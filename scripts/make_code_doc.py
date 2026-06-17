"""Generate a single printable HTML document of all Quorum source code.

Ultimatix Prime Events rejects .zip uploads, so the code must be submitted as a
.doc/.pdf. Run this, open docs/source_code.html in a browser, and Print -> Save
as PDF to produce the source-code file for the submission form.
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Real source files, in a readable order. Data/doc/binary files are excluded.
FILES = [
    "README.md",
    "requirements.txt",
    "backend/schemas.py",
    "backend/config.py",
    "backend/inference.py",
    "backend/jurors.py",
    "backend/orchestrator.py",
    "backend/adjudicator.py",
    "backend/metrics.py",
    "backend/main.py",
    "backend/__init__.py",
    "eval/prepare_data.py",
    "eval/run_eval.py",
    "bench/amd_benchmark.py",
    "scripts/serve_vllm.sh",
    "scripts/smoke_test.py",
    "frontend/app/page.js",
    "frontend/app/layout.js",
    "frontend/app/globals.css",
    "frontend/next.config.mjs",
    "frontend/postcss.config.mjs",
    "frontend/package.json",
]

HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Quorum - Source Code</title>
<style>
  body { font-family: "Segoe UI", system-ui, Arial, sans-serif; color:#0f172a; margin:0; }
  .cover { padding:60px; }
  h1 { font-size:34px; margin:0 0 6px; }
  .sub { color:#475569; font-size:18px; }
  .toc { margin-top:24px; font-size:14px; color:#334155; }
  .toc li { margin:3px 0; }
  h2 { font-size:18px; background:#0f172a; color:#fff; padding:8px 12px;
       margin:0; border-radius:6px 6px 0 0; page-break-after:avoid; }
  pre { background:#f8fafc; border:1px solid #e2e8f0; border-top:none;
        margin:0 0 26px; padding:14px 16px; font-size:11px; line-height:1.4;
        font-family:Consolas,"Courier New",monospace; white-space:pre-wrap;
        word-break:break-word; }
  .file { page-break-inside:auto; }
  @media print { @page { margin:14mm; } }
</style></head><body>
"""


def lang(path: str) -> str:
    return Path(path).suffix.lstrip(".") or "txt"


def main() -> None:
    parts = [HEAD]
    parts.append('<div class="cover">')
    parts.append("<h1>Quorum &mdash; Source Code</h1>")
    parts.append(
        '<div class="sub">A verifiable decision engine for KYC/fraud approvals '
        "&middot; TCS &times; AMD AI Hackathon (Track 1 &mdash; Agents, AGENTS_002)"
        "<br>Author: Pratiksha Gayen &middot; "
        "Repo: https://github.com/PratikshaGayen/quorum</div>"
    )
    parts.append('<ol class="toc">')
    for f in FILES:
        parts.append(f"<li>{html.escape(f)}</li>")
    parts.append("</ol></div>")

    for f in FILES:
        p = ROOT / f
        if not p.exists():
            continue
        code = p.read_text(encoding="utf-8", errors="replace")
        parts.append('<div class="file">')
        parts.append(f"<h2>{html.escape(f)}</h2>")
        parts.append(f'<pre><code class="language-{lang(f)}">'
                     f"{html.escape(code)}</code></pre>")
        parts.append("</div>")

    parts.append("</body></html>")
    out = ROOT / "docs" / "source_code.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out} ({len(FILES)} files)")


if __name__ == "__main__":
    main()
