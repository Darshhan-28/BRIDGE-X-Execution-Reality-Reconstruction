import type { ReactNode } from 'react';
import type { Candidate, ExecGraph, Gate } from './types';

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function toneForBucket(b: string): string {
  return { CONFLICT: 'bad', HIGH: 'ok', MEDIUM: 'warn', LOW: 'mut', UNMATCHED: 'mut' }[b] || 'mut';
}
export function toneForGate(d: string): string {
  return { PROPOSE: 'ok', REVIEW: 'warn', UNMATCHED: 'mut' }[d] || 'mut';
}
export function toneForStatus(s: string): string {
  return s === 'Complete' ? 'ok' : s === 'In Progress' ? 'warn' : 'mut';
}

export function GateBadge({ gate }: { gate: Gate }) {
  return (
    <span className="badges">
      <Badge tone={toneForGate(gate.decision)}>{gate.decision}</Badge>
      <Badge tone="mut">{gate.tier} · margin {gate.margin}</Badge>
      {gate.forced && <Badge tone="warn">forced review</Badge>}
    </span>
  );
}

export function DecisionBanner({ gate, granularityType }: { gate: Gate; granularityType: string }) {
  const tone = gate.decision === 'PROPOSE' ? 'ok' : gate.decision === 'REVIEW' ? 'warn' : 'mut';
  const verb = gate.decision === 'PROPOSE'
    ? 'Safe to propose as a schedule update — a planner still approves it in Review.'
    : gate.decision === 'REVIEW'
      ? 'Not automated. A planner must decide in the Review Queue.'
      : 'No confident link. Routed to investigation, not to the schedule.';
  return (
    <div className={`decision ${tone}`}>
      <b>Decision: {gate.decision}</b>
      <span className="mut">{granularityType} · {gate.tier} tier · margin {gate.margin}</span>
      <span>{verb}</span>
      {gate.reasons.map((r, i) => <span key={i} className="mut">· {r}</span>)}
    </div>
  );
}

export function ScoreBar({ score }: { score: number }) {
  const tone = score >= 85 ? 'ok' : score >= 60 ? 'warn' : 'bad';
  return (
    <div className="scorebar" title={`${score}%`}>
      <div className={`fill ${tone}`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      <span>{score}%</span>
    </div>
  );
}

export function WhyCard({ candidate }: { candidate: Candidate }) {
  const entries = Object.entries(candidate.signals);
  return (
    <div className="why">
        <div className="why-head">
          <code>{candidate.activity_code}</code>
          {candidate.activity_name && <span className="mut">{candidate.activity_name}</span>}
          {(candidate.vocab_bonus || 0) > 0 && (
            <span className="sig on" title={`Learned project vocabulary added +${candidate.vocab_bonus} to base ${candidate.base_score}`}>
              learned +{candidate.vocab_bonus}
            </span>
          )}
        </div>
      <ScoreBar score={candidate.score} />
      <div className="signals">
        {entries.map(([k, v]) => (
          <span key={k} className={`sig ${v >= 1 ? 'on' : v > 0 ? 'part' : 'off'}`} title={`${k}: ${v}`}>
            {k} {v}
          </span>
        ))}
      </div>
      <ul className="why-list">
        {candidate.why.map((w, i) => <li key={i}>{w}</li>)}
      </ul>
    </div>
  );
}

export function PipelineStrip({ active }: { active?: string }) {
  const steps = ['FIELD', 'UNDERSTOOD', 'LINKED', 'VERIFIED', 'REVIEW/UPDATED'];
  return (
    <div className="pipeline">
      {steps.map((s, i) => (
        <span key={s} className="pstep-wrap">
          <span className={`pstep ${active === s ? 'active' : ''}`}>{s}</span>
          {i < steps.length - 1 && <span className="parrow">→</span>}
        </span>
      ))}
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="mut">Loading {what}…</p>;
}
export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="error-box">
      <p>Backend unreachable or request failed: {error}</p>
      {retry && <button type="button" onClick={retry}>Retry</button>}
    </div>
  );
}
export function Empty({ text }: { text: string }) {
  return <p className="mut">{text}</p>;
}

export function ChainStrip({ graph }: { graph: ExecGraph }) {
  return (
    <div>
      <div className="chain">
        {graph.backbone.map((n, i) => (
          <span key={`${n.code}-${i}`} className="chain-wrap">
            <span className={`chnode ${n.direction === 'self' ? 'self' : ''}`} title={`${n.name} — ${n.status}`}>
              <code>{n.code}</code>
              <Badge tone={n.status === 'Complete' ? 'ok' : n.status === 'In Progress' ? 'warn' : 'mut'}>
                {n.status}
              </Badge>
            </span>
            {i < graph.backbone.length - 1 && <span className="parrow">→</span>}
          </span>
        ))}
      </div>
      {graph.predecessors.length > 0 && (
        <p className="mut">Predecessors (FS): {graph.predecessors.map((p) => `${p.code} [${p.status}]`).join(', ')}</p>
      )}
      {graph.successors.length > 0 && (
        <p className="mut">Successors (FS): {graph.successors.map((s) => `${s.code} [${s.status}]`).join(', ')}</p>
      )}
      {graph.warnings.map((w, i) => (
        <p key={i} className="errline">{w.message} <span className="mut">({w.kind}, rel {w.rel_type})</span></p>
      ))}
      {graph.reasons.map((r, i) => <p key={`r${i}`} className="mut">{r}</p>)}
      {graph.latest_review && (
        <p className="mut">Latest P7 review: {graph.latest_review.report} → {graph.latest_review.decision}.</p>
      )}
    </div>
  );
}
