import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Activity, MatchRun, QueueItem } from '../types';
import { Badge, Empty, ErrorBox, GateBadge, Loading, PipelineStrip, ScoreBar, toneForBucket } from '../components';

const BUCKETS = ['', 'HIGH', 'MEDIUM', 'LOW', 'CONFLICT', 'UNMATCHED'];

export default function Review() {
  const [params, setParams] = useSearchParams();
  const bucket = params.get('bucket') || '';
  const [items, setItems] = useState<QueueItem[]>([]);
  const [acts, setActs] = useState<Activity[]>([]);
  const [sel, setSel] = useState<string>('');
  const [detail, setDetail] = useState<MatchRun | null>(null);
  const [actor, setActor] = useState('planner');
  const [reason, setReason] = useState('');
  const [force, setForce] = useState(false);
  const [remapTo, setRemapTo] = useState('');
  const [mergeInto, setMergeInto] = useState('');
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function refresh(keepSel = true) {
    const q = await api.queue(bucket);
    setItems(q);
    if (keepSel && sel) {
      try { setDetail(await api.matchGet(sel)); } catch { setDetail(null); }
    }
  }

  useEffect(() => {
    api.activities().then(setActs).catch(() => undefined);
    refresh(false).catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bucket]);

  async function open(code: string) {
    setSel(code); setNotice(''); setError('');
    try { setDetail(await api.matchGet(code)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function act(kind: string) {
    if (!sel) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const base = { report_code: sel, actor: actor || 'planner', reason, force };
      if (kind === 'approve') await api.approve(base);
      else if (kind === 'reject') await api.reject(base);
      else if (kind === 'remap') {
        if (!remapTo) throw new Error('Choose a target activity first.');
        await api.remap({ ...base, activity_code: remapTo });
      } else if (kind === 'mark-new') await api.markNew({ ...base, activity_name: newName });
      else if (kind === 'merge') {
        if (!mergeInto) throw new Error('Choose the report to merge into first.');
        await api.merge({ ...base, into_report_code: mergeInto });
      }
      setNotice(`${kind} recorded for ${sel}.`);
      setReason(''); setForce(false);
      await refresh(true);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  const selItem = items.find((i) => i.report_code === sel);

  return (
    <div>
      <h2>Planner Decision (Human Authorization)</h2>
      <p className="mut">What decision: authorize this evidence as a verified actual — approve, reject, remap, mark new, or merge?</p>
      <PipelineStrip active="AUTHORIZATION" />
      <div className="formrow">
        <label>Bucket
          <select value={bucket} onChange={(e) => setParams(e.target.value ? { bucket: e.target.value } : {})}>
            {BUCKETS.map((b) => <option key={b} value={b}>{b || 'All'}</option>)}
          </select>
        </label>
      </div>
      {error && <ErrorBox error={error} retry={() => refresh(true).catch(() => undefined)} />}
      {notice && <p className="okline">{notice}</p>}
      <div className="cols">
        <section className="card">
          <h3>Items ({items.length})</h3>
          {items.length === 0 && <Empty text="Queue is empty for this bucket. No items need a planner decision — try another bucket or run Reconciliation first." />}
          {items.map((i) => (
            <button type="button" key={i.report_code}
              className={`qitem ${sel === i.report_code ? 'sel' : ''}`}
              onClick={() => open(i.report_code)}>
              <Badge tone={toneForBucket(i.bucket)}>{i.bucket}</Badge>
              <code>{i.report_code}</code>
              <span className="mut">{i.top_activity} · {i.top_score}% · {i.decision.state}</span>
            </button>
          ))}
        </section>
        <section className="card">
          <h3>Planner decision {sel ? <code>{sel}</code> : ''}</h3>
          {!sel && <Empty text="Select a queue item. Ambiguous matches and verification conflicts wait here instead of auto-updating the schedule." />}
          {selItem && (
            <div className="kv">
              <span>top</span><b>{selItem.top_activity} · {selItem.top_score}% (margin {selItem.margin})</b>
              <span>gate</span><span><GateBadge gate={selItem.gate} /></span>
              <span>state</span><b>{selItem.decision.state}{selItem.decision.target ? ` → ${selItem.decision.target}` : ''}</b>
            </div>
          )}
          {detail?.verification?.errors.map((e, i) => <p key={i} className="errline">{e}</p>)}
          <div className="formrow">
            <label>Actor <input value={actor} onChange={(e) => setActor(e.target.value)} /></label>
            <label className="check"><input type="checkbox" checked={force}
              onChange={(e) => setForce(e.target.checked)} /> force override</label>
          </div>
          <label>Reason (required for override / reject / remap / mark-new / merge)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
          </label>
          <div className="btnrow">
            <button type="button" disabled={busy || !sel} onClick={() => act('approve')}>Approve</button>
            <button type="button" disabled={busy || !sel} onClick={() => act('reject')}>Reject</button>
          </div>
          <div className="formrow">
            <label>Remap to
              <select value={remapTo} onChange={(e) => setRemapTo(e.target.value)}>
                <option value="">—</option>
                {acts.map((a) => <option key={a.code} value={a.code}>{a.code} · {a.name.slice(0, 40)}</option>)}
              </select>
            </label>
            <button type="button" disabled={busy || !sel} onClick={() => act('remap')}>Remap</button>
          </div>
          <div className="formrow">
            <label>New activity title
              <input value={newName} onChange={(e) => setNewName(e.target.value)}
                placeholder="Optional working title" />
            </label>
            <button type="button" disabled={busy || !sel} onClick={() => act('mark-new')}>Mark new</button>
          </div>
          <div className="formrow">
            <label>Merge into
              <select value={mergeInto} onChange={(e) => setMergeInto(e.target.value)}>
                <option value="">—</option>
                {items.filter((i) => i.report_code !== sel).map((i) => (
                  <option key={i.report_code} value={i.report_code}>{i.report_code}</option>
                ))}
              </select>
            </label>
            <button type="button" disabled={busy || !sel} onClick={() => act('merge')}>Merge</button>
          </div>
          {detail && (
            <details>
              <summary>Candidates & scores</summary>
              {detail.candidates.map((c) => (
                <div key={c.activity_code} className="row"><code>{c.activity_code}</code><ScoreBar score={c.score} /></div>
              ))}
            </details>
          )}
          {busy && <Loading what="decision" />}
        </section>
      </div>
    </div>
  );
}
