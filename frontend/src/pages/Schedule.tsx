import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { activitiesCsv, activitiesP6Xml, download } from '../export';
import type { Activity } from '../types';
import { Badge, Empty, ErrorBox, Loading, PipelineStrip, toneForStatus } from '../components';

const DAY = 86400000;

export default function Schedule() {
  const [acts, setActs] = useState<Activity[]>([]);
  const [disc, setDisc] = useState('');
  const [error, setError] = useState('');

  function load(d: string) {
    setError('');
    api.activities(d).then(setActs).catch((e: Error) => setError(e.message));
  }

  useEffect(() => { load(disc); }, [disc]);

  const range = useMemo(() => {
    const ds = acts.flatMap((a) => [a.planned_start, a.planned_finish, a.actual_start || '', a.actual_finish || ''])
      .filter(Boolean).sort();
    if (!ds.length) return null;
    const lo = new Date(ds[0]).getTime();
    const hi = new Date(ds[ds.length - 1]).getTime() + DAY;
    return { lo, span: Math.max(DAY, hi - lo) };
  }, [acts]);

  function bar(a: Activity, key: 'planned' | 'actual'): { left: string; width: string } | null {
    if (!range) return null;
    const s = key === 'planned' ? a.planned_start : a.actual_start;
    const f = key === 'planned' ? a.planned_finish : a.actual_finish;
    if (!s) return null;
    const end = f || new Date().toISOString().slice(0, 10);
    const left = ((new Date(s).getTime() - range.lo) / range.span) * 100;
    const width = Math.max(1.5, ((new Date(end).getTime() - new Date(s).getTime() + DAY) / range.span) * 100);
    return { left: `${left}%`, width: `${width}%` };
  }

  if (error) return <ErrorBox error={error} retry={() => load(disc)} />;
  if (!acts.length && !error) return <Loading what="schedule" />;

  return (
    <div>
      <h2>Schedule Intelligence</h2>
      <PipelineStrip active="REVIEW/UPDATED" />
      <div className="banner">Synthetic demonstration data — not real Oil India data. Simplified view, not a Primavera replacement.</div>
      <div className="formrow">
        <label>Discipline
          <select value={disc} onChange={(e) => setDisc(e.target.value)}>
            <option value="">All</option>
            {['Piping', 'Civil', 'Electrical', 'Mechanical', 'Instrumentation'].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => download('schedule_update.csv', activitiesCsv(acts), 'text/csv')}>
          Export CSV
        </button>
        <button type="button" onClick={() => download('schedule_update.json', JSON.stringify(acts, null, 1), 'application/json')}>
          Export JSON
        </button>
        <button type="button" onClick={() => download('schedule_prototype.xml', activitiesP6Xml(acts), 'application/xml')}>
          Export P6 XML (prototype)
        </button>
      </div>
      <p className="mut">P6 XML is a minimal prototype — validate before production import.</p>
      {acts.length === 0 && <Empty text="No activities for this filter." />}
      <div className="gantt">
        <div className="grow ghead"><span>Activity</span><span>Planned</span><span>Actual</span></div>
        {acts.map((a) => {
          const p = bar(a, 'planned');
          const v = bar(a, 'actual');
          return (
            <div key={a.code} className="grow">
              <span className="glabel" title={a.name}>
                <code>{a.code}</code> {a.name.slice(0, 42)}
                <Badge tone={toneForStatus(a.status)}>{a.status} {a.progress}%</Badge>
              </span>
              <span className="gtrack">{p && <span className="gbar plan" style={{ left: p.left, width: p.width }} />}</span>
              <span className="gtrack">{v ? <span className="gbar act" style={{ left: v.left, width: v.width }} /> : <span className="mut">—</span>}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
