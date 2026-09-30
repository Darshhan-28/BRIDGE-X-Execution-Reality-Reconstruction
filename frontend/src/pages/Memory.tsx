import { useEffect, useState } from 'react';
import { api } from '../api';
import type { DomainTerm, Patterns, SourceDocument, VocabTerm } from '../types';
import { Badge, Empty, ErrorBox, Loading, PipelineStrip } from '../components';

export default function Memory() {
  const [vocab, setVocab] = useState<VocabTerm[]>([]);
  const [patterns, setPatterns] = useState<Patterns | null>(null);
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [terms, setTerms] = useState<DomainTerm[]>([]);
  const [term, setTerm] = useState('');
  const [ctype, setCtype] = useState('object');
  const [cvalue, setCvalue] = useState('');
  const [disc, setDisc] = useState('Piping');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    const [v, p] = await Promise.all([api.vocabulary(), api.patterns()]);
    setVocab(v); setPatterns(p);
    try {
      const [s, t] = await Promise.all([api.knowledgeSources(), api.knowledgeTerms()]);
      setSources(s); setTerms(t);
    } catch { setSources([]); setTerms([]); }
  }
  useEffect(() => { load().catch((e: Error) => setError(e.message)); }, []);

  async function addTerm() {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.vocabularyAdd({ term, canonical_type: ctype, canonical_value: cvalue, discipline: disc });
      setNotice(`Term "${term}" recorded with planner provenance.`);
      setTerm(''); setCvalue('');
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  if (error && !patterns) return <ErrorBox error={error} retry={() => load().catch((e: Error) => setError(e.message))} />;
  if (!patterns) return <Loading what="memory" />;

  return (
    <div>
      <h2>Project Memory</h2>
      <p className="mut">What decision: which learned terms can be trusted in future reconciliation? Only human-approved vocabulary teaches.</p>
      <PipelineStrip active="AUTHORIZATION" />
      <div className="banner">Synthetic demonstration data — not real project data. Vocabulary is learned only from human approvals.</div>
      <div className="cols">
        <section className="card">
          <h3>Learned terminology ({vocab.length})</h3>
          <p className="mut">Approved terms actively contribute bounded bonus evidence to future linking; contributions show as [vocab] lines on Linker WHY cards.</p>
          {vocab.length === 0 && <Empty text="Nothing learned yet — approve or remap a review item first." />}
          {vocab.map((v) => (
            <div key={`${v.term}|${v.canonical_type}|${v.canonical_value}`} className="row wrap">
              <span><code>{v.term}</code> <span className="mut">({v.canonical_type})</span> → <b>{v.canonical_value}</b></span>
              <span><Badge tone="ok">×{v.approval_count}</Badge> <span className="mut">{v.source_reports.join(', ')}</span></span>
            </div>
          ))}
          <h3>Curate a term (explicit human action)</h3>
          <div className="formrow">
            <label>Term <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="e.g. x-ray" /></label>
            <label>Type
              <select value={ctype} onChange={(e) => setCtype(e.target.value)}>
                <option value="object">object</option><option value="action">action</option><option value="phrase">phrase</option>
              </select>
            </label>
            <label>Canonical <input value={cvalue} onChange={(e) => setCvalue(e.target.value)} placeholder="e.g. weld" /></label>
            <label>Discipline
              <select value={disc} onChange={(e) => setDisc(e.target.value)}>
                {['Piping', 'Civil', 'Electrical', 'Mechanical', 'Instrumentation'].map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <button type="button" disabled={busy || !term.trim() || !cvalue.trim()} onClick={addTerm}>
              {busy ? 'Adding…' : 'Add term'}
            </button>
          </div>
          {notice && <p className="okline">{notice}</p>}
          {error && <ErrorBox error={error} />}
        </section>
        <section className="card">
          <h3>Execution patterns <Badge tone="warn">synthetic</Badge></h3>
          {Object.entries(patterns.by_discipline).map(([d, s]) => (
            <div key={d} className="row wrap">
              <span><b>{d}</b> <span className="mut">{s.executions} runs</span></span>
              <span>planned {s.avg_planned_days}d → actual {s.avg_actual_days}d
                (<b className={s.avg_overrun_days > 0 ? 'neg' : 'pos'}>{s.avg_overrun_days > 0 ? '+' : ''}{s.avg_overrun_days}d</b>)</span>
            </div>
          ))}
          {patterns.patterns.map((p) => (
            <details key={p.pattern}>
              <summary>{p.pattern} <span className="mut">({p.discipline}, {p.executions}×, +{p.overrun_days}d)</span></summary>
              <p className="mut">Common issues: {p.common_issues.join('; ')}</p>
            </details>
          ))}
          <h3>Live delays by discipline</h3>
          {Object.entries(patterns.delays_by_discipline).map(([d, n]) => (
            <div key={d} className="row"><span>{d}</span><span>{n} overdue</span></div>
          ))}
        </section>
      </div>
      <section className="card">
        <h3>Public OIL knowledge <Badge tone="ok">REAL_PUBLIC</Badge></h3>
        <p className="mut">Terminology reference from public Oil India documents with provenance. Context only — never schedule, DPR, or execution data. Nothing here influences matching until a planner explicitly promotes a term.</p>
        {sources.length === 0 && <Empty text="No public sources loaded — POST /api/seed loads them." />}
        {sources.map((s) => (
          <details key={s.source_id}>
            <summary><Badge tone="ok">{s.source_type}</Badge> {s.title} <span className="mut">({s.publisher}{s.publication_date ? `, ${s.publication_date}` : ''})</span></summary>
            <p className="mut">{s.source_url}</p>
            <p className="mut">{s.document_type} · retrieved {s.retrieved_at} · {s.notes}</p>
          </details>
        ))}
        <p className="mut">{terms.length} curated domain terms (e.g. {terms.slice(0, 5).map((t) => t.term).join(', ')}{terms.length > 5 ? ', …' : ''}). Provenance per term via GET /api/knowledge/lookup.</p>
      </section>
    </div>
  );
}
