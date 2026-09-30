import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Activity, AuditEvent, Dashboard as Dash, QueueItem, RiskBoard } from '../types';
import { Badge, Empty, ErrorBox, Loading, PipelineStrip, toneForBucket } from '../components';

export default function Dashboard() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [delayed, setDelayed] = useState(0);
  const [board, setBoard] = useState<RiskBoard | null>(null);
  const [sigFilter, setSigFilter] = useState('');
  const [error, setError] = useState('');
  const [resetting, setResetting] = useState(false);

  async function load() {
    setError('');
    try {
      const [d, q, a, acts, b] = await Promise.all([
        api.dashboard(), api.queue(), api.audit(), api.activities(), api.riskBoard(),
      ]);
      setDash(d); setQueue(q); setAudit(a.slice(-6).reverse()); setBoard(b);
      const today = new Date().toISOString().slice(0, 10);
      setDelayed(acts.filter((x: Activity) => x.status !== 'Complete' && x.planned_finish < today).length);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  useEffect(() => { load(); }, []);

  async function resetDemo() {
    if (!window.confirm('Reseed the synthetic demo database? Review decisions, updates and audit history will be cleared.')) return;
    setResetting(true); setError('');
    try { await api.seed(); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setResetting(false); }
  }

  if (error && !dash) return <ErrorBox error={error} retry={load} />;
  if (!dash) return <Loading what="dashboard" />;

  const stats: [string, number, string][] = [
    ['Activities', dash.activities, '/schedule'],
    ['Field reports', dash.reports, '/field'],
    ['Pending review', queue.filter((q) => q.decision.state === 'pending').length, '/review'],
    ['Conflicts', dash.conflicts, '/linker'],
    ['Delayed (live)', delayed, '/schedule'],
    ['Unmatched', (dash.reports_by_category.unmatched || 0), '/field'],
  ];
  const buckets: Record<string, number> = {};
  for (const q of queue) buckets[q.bucket] = (buckets[q.bucket] || 0) + 1;

  return (
    <div>
      <h2>Dashboard</h2>
      <PipelineStrip active="FIELD" />
      <div className="banner">Synthetic demonstration data — not real Oil India data.</div>
      {error && <ErrorBox error={error} retry={load} />}
      <div className="formrow">
        <button type="button" disabled={resetting} onClick={resetDemo} title="Reseed the synthetic demo database">
          {resetting ? 'Resetting…' : 'Reset demo data'}
        </button>
      </div>
      <div className="grid">
        {stats.map(([label, n, to]) => (
          <Link key={label} to={to} className="stat">
            <span className="num">{n}</span>
            <span className="lbl">{label}</span>
          </Link>
        ))}
      </div>
      <div className="cols">
        <section className="card">
          <h3>Review queue by bucket</h3>
          {queue.length === 0 && <Empty text="No match runs yet. Run the Linker or Field Intelligence first." />}
          {Object.entries(buckets).map(([b, n]) => (
            <div key={b} className="row">
              <Badge tone={toneForBucket(b)}>{b}</Badge>
              <span>{n}</span>
              <Link to={`/review?bucket=${b}`}>open</Link>
            </div>
          ))}
          <h3>Reports by category</h3>
          {Object.entries(dash.reports_by_category).map(([c, n]) => (
            <div key={c} className="row"><span>{c}</span><span>{n}</span></div>
          ))}
        </section>
        <section className="card">
          <h3>Activities by discipline / status</h3>
          {Object.entries(dash.activities_by_discipline).map(([d, n]) => (
            <div key={d} className="row"><span>{d}</span><span>{n}</span></div>
          ))}
          {Object.entries(dash.activities_by_status).map(([s, n]) => (
            <div key={s} className="row"><span className="mut">{s}</span><span>{n}</span></div>
          ))}
          <h3>Latest audit events</h3>
          {audit.length === 0 && <Empty text="No consequential actions yet." />}
          {audit.map((a) => (
            <div key={a.id} className="row">
              <span><code>{a.action}</code> {a.report_code} <span className="mut">by {a.actor}</span></span>
              <Link to="/audit">view</Link>
            </div>
          ))}
        </section>
      </div>
      <section className="card">
        <h3>Execution Intelligence / Attention Signals</h3>
        <p className="mut">Advisory only — derived from stored schedule, verification, graph, and synthetic history evidence. Not a prediction.</p>
        <div className="formrow">
          <label>Signal
            <select value={sigFilter} onChange={(e) => setSigFilter(e.target.value)}>
              <option value="">All signals</option>
              {board && Object.keys(board.summary.by_signal).sort().map((s) => (
                <option key={s} value={s}>{s} ({board.summary.by_signal[s]})</option>
              ))}
            </select>
          </label>
          {board && Object.entries(board.summary.by_priority).map(([p, n]) => (
            <Badge key={p} tone={p === 'ATTENTION' ? 'bad' : p === 'WATCH' ? 'warn' : 'mut'}>
              {p}: {n}
            </Badge>
          ))}
        </div>
        {!board && <Loading what="attention signals" />}
        {board && board.items
          .filter((i) => i.priority !== 'NORMAL')
          .filter((i) => !sigFilter || i.signals.includes(sigFilter))
          .slice(0, 8)
          .map((i) => (
            <div key={`${i.subject_type}:${i.subject_id}`} className="row wrap">
              <span><code>{i.subject_id}</code> <span className="mut">{i.name.slice(0, 50)} · {i.status}</span></span>
              <span>
                <Badge tone={i.priority === 'ATTENTION' ? 'bad' : 'warn'}>{i.priority}</Badge>{' '}
                {i.signals.map((s) => <Badge key={s} tone="mut">{s}</Badge>)}
              </span>
              <span className="mut" style={{ flexBasis: '100%' }}>{i.reasons[0] || ''}</span>
            </div>
          ))}
        {board && (
          <p className="mut">{board.note}</p>
        )}
      </section>
    </div>
  );
}
