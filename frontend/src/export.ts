import type { Activity } from './types';

export function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function csvCell(v: unknown): string {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function activitiesCsv(acts: Activity[]): string {
  const head = ['code', 'name', 'discipline', 'location', 'status', 'progress',
    'planned_start', 'planned_finish', 'actual_start', 'actual_finish'];
  const rows = acts.map((a) => head.map((h) => csvCell((a as unknown as Record<string, unknown>)[h])).join(','));
  return [head.join(','), ...rows].join('\n');
}

/** Minimal P6-compatible-style export. Prototype — validate before production import. */
export function activitiesP6Xml(acts: Activity[]): string {
  const esc = (s: unknown) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const items = acts.map((a, i) => [
    '    <Activity>',
    `      <Id>${i + 1}</Id>`,
    `      <ActivityId>${esc(a.code)}</ActivityId>`,
    `      <Name>${esc(a.name)}</Name>`,
    `      <PlannedStart>${esc(a.planned_start)}</PlannedStart>`,
    `      <PlannedFinish>${esc(a.planned_finish)}</PlannedFinish>`,
    `      <ActualStart>${esc(a.actual_start)}</ActualStart>`,
    `      <ActualFinish>${esc(a.actual_finish)}</ActualFinish>`,
    `      <PercentComplete>${esc(a.progress)}</PercentComplete>`,
    `      <Status>${esc(a.status)}</Status>`,
    '    </Activity>',
  ].join('\n')).join('\n');
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!-- BRIDGE-X prototype export. Prototype — validate before production import into P6. -->',
    '<!-- Synthetic demonstration data — not real project data. -->',
    '<Project>',
    '  <Name>BRIDGE-X Demo Refinery Upgrade (Synthetic)</Name>',
    '  <Activities>',
    items,
    '  </Activities>',
    '</Project>',
  ].join('\n');
}
