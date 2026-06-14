"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const COLORS = {
  APPROVE: { bg: "bg-emerald-950", border: "border-emerald-500", text: "text-emerald-400" },
  REJECT: { bg: "bg-red-950", border: "border-red-500", text: "text-red-400" },
  ABSTAIN: { bg: "bg-zinc-800", border: "border-zinc-500", text: "text-zinc-400" },
  ESCALATE: { bg: "bg-amber-950", border: "border-amber-500", text: "text-amber-400" },
};

function Badge({ decision, big }) {
  const c = COLORS[decision] || COLORS.ABSTAIN;
  return (
    <span className={`${c.bg} ${c.border} ${c.text} border rounded-md font-bold ${big ? "px-4 py-2 text-2xl" : "px-2 py-0.5 text-sm"}`}>
      {decision}
    </span>
  );
}

function ConfidenceBar({ value }) {
  return (
    <div className="h-2 w-full rounded bg-zinc-700">
      <div className="h-2 rounded bg-sky-400" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

function JurorCard({ v }) {
  const c = COLORS[v.decision] || COLORS.ABSTAIN;
  return (
    <div className={`${c.bg} ${c.border} border rounded-lg p-4 flex flex-col gap-2`}>
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-zinc-300">{v.juror_id}</span>
        <Badge decision={v.decision} />
      </div>
      <ConfidenceBar value={v.confidence} />
      <span className="text-xs text-zinc-400">confidence {(v.confidence * 100).toFixed(0)}%</span>
      <p className="text-sm text-zinc-200">{v.rationale}</p>
      {v.flags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {v.flags.map((f) => (
            <span key={f} className="bg-zinc-800 text-amber-300 text-xs rounded px-1.5 py-0.5">⚑ {f}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState("");
  const [decision, setDecision] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/cases`)
      .then((r) => r.json())
      .then((d) => {
        setCases(d);
        if (d.length) setSelected(d[0].case_id);
      })
      .catch(() => setError(`Cannot reach backend at ${API}. Is uvicorn running?`));
  }, []);

  async function deliberate(caseId) {
    const c = cases.find((x) => x.case_id === caseId);
    if (!c) return;
    setLoading(true);
    setDecision(null);
    setError("");
    try {
      const r = await fetch(`${API}/api/deliberate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: c.case_id, profile: c.profile, narrative: c.narrative }),
      });
      if (!r.ok) throw new Error(await r.text());
      setDecision(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const selectedCase = cases.find((x) => x.case_id === selected);
  const baseline = decision?.baseline_verdict;

  return (
    <main className="mx-auto max-w-6xl p-6 flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-bold">Quorum</h1>
        <p className="text-zinc-400">
          We don't make AI smarter — we make its decisions trustworthy and auditable.
        </p>
      </header>

      {/* Zone 1: case input */}
      <section className="rounded-lg border border-zinc-700 p-4 flex flex-col gap-3">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400">1 · Case</h2>
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="bg-zinc-900 border border-zinc-600 rounded px-3 py-2"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {cases.map((c) => (
              <option key={c.case_id} value={c.case_id}>{c.case_id}</option>
            ))}
          </select>
          <button
            onClick={() => deliberate(selected)}
            disabled={loading || !selected}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded px-4 py-2 font-semibold"
          >
            {loading ? "Deliberating…" : "Deliberate"}
          </button>
          <button
            onClick={() => { setSelected("DEMO-FRAUD"); deliberate("DEMO-FRAUD"); }}
            disabled={loading}
            className="bg-red-700 hover:bg-red-600 disabled:opacity-40 rounded px-4 py-2 font-semibold"
          >
            ▶ Demo case (planted fraud)
          </button>
        </div>
        {selectedCase && (
          <p className="text-sm text-zinc-300 border-l-2 border-zinc-600 pl-3">{selectedCase.narrative}</p>
        )}
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </section>

      {/* Zone 2: live jury view */}
      {decision && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm uppercase tracking-wide text-zinc-400">2 · The Jury</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {decision.all_verdicts.map((v) => <JurorCard key={v.juror_id} v={v} />)}
          </div>
        </section>
      )}

      {/* Zone 3: verdict panel */}
      {decision && (
        <section className="rounded-lg border border-zinc-700 p-5 flex flex-col gap-4">
          <h2 className="text-sm uppercase tracking-wide text-zinc-400">3 · Adjudicated Verdict</h2>
          <div className="flex flex-wrap items-center gap-6">
            <Badge decision={decision.final_decision} big />
            <div>
              <div className="text-xs text-zinc-400">panel confidence</div>
              <div className="text-xl font-bold">{(decision.panel_confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div className="text-xs text-zinc-400">agreement</div>
              <div className="text-xl font-bold">{(decision.agreement_ratio * 100).toFixed(0)}%</div>
            </div>
            {baseline && (
              <div className={`ml-auto rounded-md border px-4 py-2 ${COLORS[baseline.decision].border}`}>
                <div className="text-xs text-zinc-400">Single model said</div>
                <div className={`text-lg font-bold ${COLORS[baseline.decision].text}`}>
                  {baseline.decision} ({(baseline.confidence * 100).toFixed(0)}%)
                </div>
              </div>
            )}
          </div>

          {baseline && baseline.decision !== decision.final_decision && (
            <div className="rounded bg-amber-950 border border-amber-600 text-amber-200 text-sm p-3">
              ⚠ The single model said <b>{baseline.decision}</b>, but the jury returned{" "}
              <b>{decision.final_decision}</b>. A solo LLM would have waved this through.
            </div>
          )}

          <p className="text-sm text-zinc-300">{decision.rationale_summary}</p>

          {decision.dissent_report.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-zinc-400 mb-2">Dissent report (audit trail)</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {decision.dissent_report.map((v) => <JurorCard key={v.juror_id} v={v} />)}
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
