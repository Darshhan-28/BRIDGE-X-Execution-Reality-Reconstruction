import { useState } from 'react';
import { api } from '../api';
import type { ExecGraph, FieldEvent, MatchRun } from '../types';
import { Badge, ChainStrip, DecisionBanner, ErrorBox, GateBadge, Loading, PipelineStrip, ScoreBar, WhyCard } from '../components';

type Step = 'idle' | 'ingested' | 'matched';

export default function FieldIntelligence() {
  const [text, setText] = useState('24 inch spool erection completed at R-204 on 18 Sep 2026.');
  const [file, setFile] = useState<File | null>(null);
  const [reportCode, setReportCode] = useState('');
  const [rawEcho, setRawEcho] = useState('');
  const [reportSourceType, setReportSourceType] = useState('');
  const [analyzeInfo, setAnalyzeInfo] = useState('');
  const [run, setRun] = useState<MatchRun | null>(null);
  const [graph, setGraph] = useState<ExecGraph | null>(null);
  const [step, setStep] = useState<Step>('idle');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function ingest() {
    setBusy(true); setError(''); setRun(null);
    try {
      if (file) {
        const res = await api.analyzeFile(file);
        if (res.inserted === 0) {
          setAnalyzeInfo(`No records inserted. ${res.warnings.join(' ')}`);
          setStep('idle');
        } else {
          const code = res.report_codes[0];
          setReportCode(code);
          setRawEcho(`(from ${file.name}) first of ${res.inserted} inserted: ${code}`);
          try {
            const recs = await api.reports();
            setReportSourceType(recs.find((r) => r.report_code === code)?.source_type || 'USER_PROVIDED');
          } catch { setReportSourceType('USER_PROVIDED'); }
          setAnalyzeInfo(res.warnings.length ? `Warnings: ${res.warnings.join(' ')}` : '');
          setStep('ingested');
        }
      } else {
        if (!text.trim()) throw new Error('Paste report text or choose a file.');
        const rec = await api.ingestText({ raw_text: text });
        setReportCode(rec.report_code);
        setRawEcho(rec.raw_text);
        setReportSourceType(rec.source_type || 'USER_PROVIDED');
        setAnalyzeInfo('');
        setStep('ingested');
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function runPipeline() {
    if (!reportCode) return;
    setBusy(true); setError(''); setGraph(null);
    try {
      const m = await api.matchRun({ report_code: reportCode });
      setRun(m);
      setStep('matched');
      if (m.candidates.length > 0) {
        try { setGraph(await api.graph(m.candidates[0].activity_code, 2, reportCode)); }
        catch { setGraph(null); }
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  const ev: FieldEvent | undefined = run?.event;
  const stage = step === 'matched' ? 'REVIEW/UPDATED' : step === 'ingested' ? 'UNDERSTOOD' : 'FIELD';

  return (
    <div>
      <h2>Field Intelligence</h2>
      <PipelineStrip active={stage} />
      <section className="card">
        <h3>1 · Ingest field evidence</h3>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
          placeholder="Free-text field report…" />
        <div className="formrow">
          <input type="file" accept=".csv,.xlsx,.xls,.pdf,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button type="button" disabled={busy} onClick={ingest}>
            {busy ? 'Working…' : 'Ingest report'}
          </button>
        </div>
        {analyzeInfo && <p className="warnline">{analyzeInfo}</p>}
        {error && <ErrorBox error={error} retry={ingest} />}
      </section>

      {step !== 'idle' && (
        <section className="card">
          <h3>2 · Original evidence</h3>
          <p><code>{reportCode}</code>{reportSourceType && <span> <Badge tone="mut">{reportSourceType}</Badge></span>}</p>
          <blockquote>{rawEcho}</blockquote>
          <button type="button" disabled={busy} onClick={runPipeline}>
            {busy ? <Loading what="pipeline" /> : '3 · Understand → Link → Verify'}
          </button>
        </section>
      )}

      {run && ev && (
        <>
          <section className="card">
            <h3>Understood event <Badge tone="mut">{ev.extractor}</Badge></h3>
            <div className="kv">
              <span>type</span><b>{ev.event_type}</b>
              <span>action/object</span><b>{ev.action || '—'} / {ev.object || '—'}</b>
              <span>size/tag</span><b>{ev.size || '—'} / {ev.tag || '—'}</b>
              <span>location</span><b>{ev.location || '—'}</b>
              <span>discipline</span><b>{ev.discipline || '—'}</b>
              <span>date</span><b>{ev.event_date || '—'}</b>
              <span>progress</span><b>{ev.progress_pct ?? '—'}</b>
            </div>
            {ev.warnings.map((w, i) => <p key={i} className="warnline">{w}</p>)}
          </section>
          <section className="card">
            <h3>Linked candidates</h3>
            {run.candidates.map((c) => (
              <div key={c.activity_code} className="cand">
                <div className="row"><code>{c.activity_code}</code><ScoreBar score={c.score} /></div>
                <WhyCard candidate={c} />
              </div>
            ))}
            {run.unmatched && <p className="warnline">{run.reason}</p>}
          </section>
          <section className="card">
            <h3>Execution Context / Dependency Chain</h3>
            {!graph && <p className="mut">Chain loads with the top candidate.</p>}
            {graph && <ChainStrip graph={graph} />}
          </section>
          <section className="card">
            <h3>Verified → decision</h3>
            {run.verification && (
              <DecisionBanner gate={run.verification.gate} granularityType={run.granularity.type} />
            )}
            <p>Granularity: <b>{run.granularity.type}</b> <span className="mut">{run.granularity.reason}</span></p>
            {run.verification && (
              <>
                <GateBadge gate={run.verification.gate} />
                {run.verification.errors.map((e, i) => <p key={i} className="errline">{e}</p>)}
                {run.verification.warnings.map((w, i) => <p key={i} className="warnline">{w}</p>)}
                {run.verification.variance.details.map((d, i) => <p key={i} className="mut">{d}</p>)}
              </>
            )}
            <p className="mut">Consequential decisions happen in the <a href="/review">Review Queue</a>
              {run.verification && <> · gate: <b>{run.verification.gate.decision}</b></>}.</p>
          </section>
        </>
      )}
    </div>
  );
}
