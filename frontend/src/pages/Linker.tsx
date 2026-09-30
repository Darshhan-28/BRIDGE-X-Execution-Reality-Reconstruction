import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ExecGraph, FieldReport, MatchRun } from '../types';
import { Badge, ChainStrip, DecisionBanner, Empty, ErrorBox, GateBadge, Loading, PipelineStrip, ScoreBar, WhyCard } from '../components';

const DEMOS: [string, string, string][] = [
  ['DPR-2026-09-18-01', 'Clean match', 'spool erection → PIP-204-017'],
  ['DPR-2026-09-19-19', 'Ambiguous', 'R204 piping → human review'],
  ['DPR-2026-09-18-26', 'Dependency error', 'welding before erection'],
];

export default function Linker() {
  const [reports, setReports] = useState<FieldReport[]>([]);
  const [code, setCode] = useState('DPR-2026-09-18-01');
  const [run, setRun] = useState<MatchRun | null>(null);
  const [graph, setGraph] = useState<ExecGraph | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.reports().then(setReports).catch((e: Error) => setError(e.message));
  }, []);

  const sourceMix = reports.length
    ? Object.entries(reports.reduce<Record<string, number>>((m, r) => {
        const k = r.source_type || 'SYNTHETIC';
        m[k] = (m[k] || 0) + 1;
        return m;
      }, {})).map(([k, n]) => `${k}: ${n}`).join(' · ')
    : '';

  async function link(loadStored = false, preset = '') {
    const target = preset || code;
    if (!target) return;
    setBusy(true); setError(''); setGraph(null);
    try {
      if (preset) setCode(preset);
      const m = loadStored ? await api.matchGet(target) : await api.matchRun({ report_code: target });
      setRun(m);
      if (m.candidates.length > 0) {
        try { setGraph(await api.graph(m.candidates[0].activity_code, 2, target)); }
        catch { setGraph(null); }
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  const margin = run && run.candidates.length > 1
    ? Math.round((run.candidates[0].score - run.candidates[1].score) * 10) / 10
    : (run?.candidates[0]?.score ?? 0);

  return (
    <div>
      <h2>Schedule Linker</h2>
      <PipelineStrip active="LINKED" />
      {sourceMix && <p className="mut">Evidence provenance — {sourceMix} (synthetic regression fixtures retained; user uploads arrive as USER_PROVIDED).</p>}
      <div className="btnrow" role="group" aria-label="Demo scenarios">
        {DEMOS.map(([c, label, hint]) => (
          <button type="button" key={c} className="chip" disabled={busy}
            title={`${c}: ${hint}`} onClick={() => link(false, c)}>
            Demo: {label}
          </button>
        ))}
      </div>
      <section className="card">
        <div className="formrow">
          <input list="reps" value={code} onChange={(e) => setCode(e.target.value)}
            placeholder="Report code, e.g. DPR-2026-09-18-01" />
          <datalist id="reps">
            {reports.map((r) => <option key={r.report_code} value={r.report_code} />)}
          </datalist>
          <button type="button" disabled={busy || !code} onClick={() => link(false)}>
            {busy ? 'Linking…' : 'Run linking'}
          </button>
          <button type="button" disabled={busy || !code} onClick={() => link(true)}>
            Reload stored run
          </button>
        </div>
        {error && <ErrorBox error={error} retry={() => link(false)} />}
      </section>

      {busy && <Loading what="candidates" />}
      {run && !busy && (
        <>
          <section className="card">
            <h3>Field event <Badge tone="mut">{run.event.extractor}</Badge></h3>
            <blockquote>{run.event.evidence_text}</blockquote>
            <div className="kv">
              <span>type</span><b>{run.event.event_type}</b>
              <span>action/object</span><b>{run.event.action || '—'} / {run.event.object || '—'}</b>
              <span>size/tag</span><b>{run.event.size || '—'} / {run.event.tag || '—'}</b>
              <span>location/discipline</span><b>{run.event.location || '—'} / {run.event.discipline || '—'}</b>
              <span>date</span><b>{run.event.event_date || '—'}</b>
            </div>
          </section>
          <section className="card">
            <h3>Candidates <span className="mut">margin {margin}</span></h3>
            {run.candidates.length === 0 && <Empty text="No candidates passed retrieval filters." />}
            {run.candidates.map((c) => (
              <div key={c.activity_code} className="cand">
                <div className="row">
                  <span><b>#{c.rank}</b> <code>{c.activity_code}</code></span>
                  <ScoreBar score={c.score} />
                </div>
                <WhyCard candidate={c} />
              </div>
            ))}
            {run.unmatched && <p className="warnline">{run.reason}</p>}
          </section>
          <section className="card">
            <h3>Execution Context / Dependency Chain</h3>
            {!graph && <Empty text="Chain loads with the top candidate." />}
            {graph && <ChainStrip graph={graph} />}
          </section>
          <section className="card">
            <h3>Granularity · Verification · Gate</h3>
            {run.verification && (
              <DecisionBanner gate={run.verification.gate} granularityType={run.granularity.type} />
            )}
            <p><b>{run.granularity.type}</b> → <code>{run.granularity.activity_codes.join(', ') || '—'}</code></p>
            <p className="mut">{run.granularity.reason}</p>
            {run.verification && (
              <>
                <GateBadge gate={run.verification.gate} />
                {run.verification.errors.map((e, i) => <p key={i} className="errline">{e}</p>)}
                {run.verification.warnings.map((w, i) => <p key={i} className="warnline">{w}</p>)}
                {run.verification.variance.details.map((d, i) => <p key={i} className="mut">{d}</p>)}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
