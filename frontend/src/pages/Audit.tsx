import { useEffect, useState } from 'react';
import { api } from '../api';
import { download } from '../export';
import type { AuditEvent } from '../types';
import { Badge, Empty, ErrorBox, Loading, PipelineStrip } from '../components';

function pretty(json: string): string {
  try { return JSON.stringify(JSON.parse(json), null, 1); }
  catch { return json; }
}

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  function load(a: string) {
    setLoading(true); setError('');
    api.audit(a ? { action: a } : {})
      .then(setEvents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(action); }, [action]);

  if (error) return <ErrorBox error={error} retry={() => load(action)} />;

  return (
    <div>
      <h2>Audit Trail (Provenance)</h2>
      <p className="mut">What decision: can this actual be traced back to evidence, verification, and the planner who authorized it?</p>
      <PipelineStrip active="AUTHORIZATION" />
      <div className="formrow">
        <label>Action
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">All</option>
            {['approve', 'reject', 'remap', 'mark_new', 'merge'].map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => download('audit_report.json', JSON.stringify(events, null, 1), 'application/json')}>
          Export audit JSON
        </button>
      </div>
      {!events && <Loading what="audit" />}
      {loading && <Loading what="audit" />}
      {!loading && events.length === 0 && <Empty text="No audit events yet — take a review action first." />}
      <div className="timeline">
        {events.map((e) => (
          <div key={e.id} className="titem">
            <div className="thead">
              <Badge tone="mut">{e.timestamp.replace('T', ' ').slice(0, 19)}</Badge>
              <Badge tone="ok">{e.action}</Badge>
              <code>{e.report_code}</code>
              <span className="mut">by {e.actor}</span>
            </div>
            <p>{e.reason || <span className="mut">no reason recorded</span>}</p>
            <details>
              <summary>before / after · {e.activity_codes}</summary>
              <div className="cols">
                <pre>{pretty(e.before_json)}</pre>
                <pre>{pretty(e.after_json)}</pre>
              </div>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
