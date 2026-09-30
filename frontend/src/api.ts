import type {
  AgentReply, AuditEvent, Conflict, Dashboard, DomainTerm, ExecGraph, FieldReport, Health,
  MatchRun, Patterns, QueueItem, RiskBoard, RiskItem, ScheduleUpdate, SourceDocument, VocabTerm, Activity,
} from './types';

export const API = import.meta.env.VITE_API_URL as string || 'http://127.0.0.1:8000';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`${r.status} ${r.statusText}${detail ? `: ${detail.slice(0, 300)}` : ''}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => req<Health>('/api/health'),
  dashboard: () => req<Dashboard>('/api/dashboard'),
  activities: (discipline = '') =>
    req<Activity[]>(`/api/activities${discipline ? `?discipline=${encodeURIComponent(discipline)}` : ''}`),
  reports: (category = '') =>
    req<FieldReport[]>(`/api/reports${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  conflicts: () => req<Conflict[]>('/api/conflicts'),
  ingestText: (body: Record<string, unknown>) =>
    req<FieldReport>('/api/reports', { method: 'POST', body: JSON.stringify(body) }),
  analyzeFile: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch(`${API}/api/reports/analyze`, { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${(await r.text()).slice(0, 300)}`);
    return r.json() as Promise<{ inserted: number; report_codes: string[]; warnings: string[]; ocr_required: boolean }>;
  },
  matchRun: (body: Record<string, unknown>) =>
    req<MatchRun>('/api/matching/run', { method: 'POST', body: JSON.stringify(body) }),
  matchGet: (code: string) => req<MatchRun>(`/api/matching/${encodeURIComponent(code)}`),
  queue: (bucket = '') =>
    req<QueueItem[]>(`/api/review/queue${bucket ? `?bucket=${encodeURIComponent(bucket)}` : ''}`),
  approve: (body: Record<string, unknown>) =>
    req<{ update_id: number; forced: boolean; after: unknown }>('/api/review/approve', { method: 'POST', body: JSON.stringify(body) }),
  reject: (body: Record<string, unknown>) => req('/api/review/reject', { method: 'POST', body: JSON.stringify(body) }),
  remap: (body: Record<string, unknown>) => req('/api/review/remap', { method: 'POST', body: JSON.stringify(body) }),
  markNew: (body: Record<string, unknown>) => req('/api/review/mark-new', { method: 'POST', body: JSON.stringify(body) }),
  merge: (body: Record<string, unknown>) => req('/api/review/merge', { method: 'POST', body: JSON.stringify(body) }),
  updates: (report_code = '') =>
    req<ScheduleUpdate[]>(`/api/schedule-updates${report_code ? `?report_code=${encodeURIComponent(report_code)}` : ''}`),
  audit: (params: Record<string, string> = {}) => {
    const q = new URLSearchParams(params).toString();
    return req<AuditEvent[]>(`/api/audit${q ? `?${q}` : ''}`);
  },
  vocabulary: (params: Record<string, string> = {}) => {
    const q = new URLSearchParams(params).toString();
    return req<VocabTerm[]>(`/api/memory/vocabulary${q ? `?${q}` : ''}`);
  },
  vocabularyAdd: (body: Record<string, unknown>) =>
    req<VocabTerm>('/api/memory/vocabulary', { method: 'POST', body: JSON.stringify(body) }),
  patterns: () => req<Patterns>('/api/memory/patterns'),
  agent: (question: string) =>
    req<AgentReply>('/api/time-agent', { method: 'POST', body: JSON.stringify({ question }) }),
  seed: () => req<Record<string, number>>('/api/seed', { method: 'POST' }),
  graph: (code: string, depth = 2, report_code = '') =>
    req<ExecGraph>(`/api/graph/${encodeURIComponent(code)}?depth=${depth}${report_code ? `&report_code=${encodeURIComponent(report_code)}` : ''}`),
  riskBoard: (project = 'BRX-DEMO-01', level = '') =>
    req<RiskBoard>(`/api/risk/project/${encodeURIComponent(project)}${level ? `?level=${encodeURIComponent(level)}` : ''}`),
  riskActivity: (code: string) => req<RiskItem>(`/api/risk/activity/${encodeURIComponent(code)}`),
  knowledgeSources: () => req<SourceDocument[]>('/api/knowledge/sources'),
  knowledgeTerms: (q = '', category = '') =>
    req<DomainTerm[]>(`/api/knowledge/terms${q || category ? `?q=${encodeURIComponent(q)}${category ? `&category=${encodeURIComponent(category)}` : ''}` : ''}`),
  knowledgeLookup: (q: string) => req<DomainTerm[]>(`/api/knowledge/lookup?q=${encodeURIComponent(q)}`),
};
