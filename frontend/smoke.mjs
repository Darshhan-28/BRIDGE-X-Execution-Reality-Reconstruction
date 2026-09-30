/* BRIDGE-X frontend smoke: export unit checks + live API contract.
 * Exports compile src/export.ts with esbuild (no new deps) and assert
 * CSV quoting, P6 rows and the prototype disclaimer.
 * API checks reseed the dev database, run the three demo pipelines and
 * assert every shape the pages consume. Backend must be up:
 *   (backend/.venv) uvicorn app.main:app --port 8000
 * Run: npm run smoke
 */
import { execFileSync, execSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)));
const API = process.env.VITE_API_URL || 'http://127.0.0.1:8000';
let failures = 0;

function check(name, cond, extra = '') {
  if (cond) console.log(`  ok   ${name}`);
  else { failures++; console.log(`  FAIL ${name} ${extra}`); }
}

async function api(path, init) {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...((init && init.headers) || {}) },
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

// ---- 1. build artifacts ----
console.log('build artifacts');
check('dist/index.html exists', existsSync(join(ROOT, 'dist', 'index.html')));
const html = existsSync(join(ROOT, 'dist', 'index.html'))
  ? readFileSync(join(ROOT, 'dist', 'index.html'), 'utf8') : '';
check('index.html references bundle', /assets\/index-.*\.js/.test(html));

// ---- 2. export functions (compiled from real source via installed tsc) ----
console.log('exports');
{
  const tmp = mkdtempSync(join(tmpdir(), 'bx-smoke-'));
  try {
    execSync(`node "${join(ROOT, 'node_modules', 'typescript', 'bin', 'tsc')}" src/export.ts --ignoreConfig --outDir "${tmp}" --module esnext --target es2020 --moduleResolution bundler --skipLibCheck`, { cwd: ROOT, stdio: 'pipe' });
  } catch (e) {
    check('export.ts compiles', false, String(e).slice(0, 200));
  }
  const compiled = join(tmp, 'export.js');
  if (!existsSync(compiled)) {
    check('export.js emitted', false);
  } else {
    const exp = await import(pathToFileURL(compiled).href);
  const rows = [
    { code: 'PIP-204-017', name: 'Erect "24in" Spool, Rack R-204', discipline: 'Piping', location: 'R-204',
      status: 'In Progress', progress: 60, planned_start: '2026-09-08', planned_finish: '2026-09-12',
      actual_start: '2026-09-08', actual_finish: null },
  ];
  const csv = exp.activitiesCsv(rows);
  check('csv header', csv.split('\n')[0] === 'code,name,discipline,location,status,progress,planned_start,planned_finish,actual_start,actual_finish');
  check('csv quoting', csv.includes('"Erect ""24in"" Spool, Rack R-204"'));
  const xml = exp.activitiesP6Xml(rows);
  check('p6 prototype disclaimer', xml.includes('Prototype — validate before production import'));
  check('p6 synthetic note', xml.includes('not real project data'));
  check('p6 activity row', xml.includes('<ActivityId>PIP-204-017</ActivityId>'));
  check('p6 xml escaping', exp.activitiesP6Xml([{ ...rows[0], name: 'A&B <test>' }]).includes('A&amp;B &lt;test&gt;'));
  }
}

// ---- 3. live API contract (reseeds dev DB, runs demo pipelines) ----
console.log('api contract');
try {
  const health = await api('/api/health');
  check('health ok (fallback ok offline)', health.status === 'ok');

  const seed = await api('/api/seed', { method: 'POST' });
  check('seed counts', seed.activities === 55 && seed.reports >= 30, JSON.stringify(seed));

  const dash = await api('/api/dashboard');
  check('dashboard shapes', dash.activities === 55 && typeof dash.reports_by_category === 'object');

  const acts = await api('/api/activities');
  check('activities shape', acts.length === 55 && acts[0].code && acts[0].planned_start !== undefined);

  const reps = await api('/api/reports');
  check('reports shape', reps.length >= 30 && reps[0].report_code && reps[0].raw_text !== undefined);

  // demo 1: clean link -> verify -> approve -> audit
  const m1 = await api('/api/matching/run', { method: 'POST', body: JSON.stringify({ report_code: 'DPR-2026-09-18-01' }) });
  check('demo1 top candidate', m1.candidates[0].activity_code === 'PIP-204-017');
  check('demo1 why cards', m1.candidates[0].why.length >= 7);
  check('demo1 verification+gate', m1.verification.valid === true && !!m1.verification.gate);
  const blocked = await fetch(`${API}/api/review/approve`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ report_code: 'DPR-2026-09-18-01' }) });
  check('demo1 gated approval (422)', blocked.status === 422);
  const ap = await api('/api/review/approve', { method: 'POST', body: JSON.stringify({ report_code: 'DPR-2026-09-18-01', force: true, reason: 'smoke' }) });
  check('demo1 forced approval', !!ap.update_id);
  const ups = await api('/api/schedule-updates?report_code=DPR-2026-09-18-01');
  check('demo1 update recorded', ups.length === 1 && ups[0].status === 'approved');
  const trail = await api('/api/audit?report_code=DPR-2026-09-18-01');
  check('demo1 audit trail', trail.some((t) => t.action === 'approve' && t.actor && t.timestamp && t.reason !== undefined));

  // demo 2: ambiguous -> group review, never auto
  const m2 = await api('/api/matching/run', { method: 'POST', body: JSON.stringify({ report_code: 'DPR-2026-09-19-19' }) });
  check('demo2 one-to-many', m2.granularity.type === 'ONE_TO_MANY' && m2.granularity.insufficient_evidence === true);

  // demo 3: welding before erection -> dependency error
  const m3 = await api('/api/matching/run', { method: 'POST', body: JSON.stringify({ report_code: 'DPR-2026-09-18-26' }) });
  check('demo3 predecessor error', m3.verification.valid === false && m3.verification.errors.some((e) => e.includes('PIP-204-018')));

  // review queue / memory / agent contracts
  const q = await api('/api/review/queue');
  check('queue shape+buckets', q.length >= 3 && q.every((i) => i.bucket && i.gate && i.decision));
  const vocab = await api('/api/memory/vocabulary');
  check('vocabulary learned from approval', vocab.some((v) => v.term === 'erect spool' && v.approval_count >= 1 && v.source_reports.length > 0));
  const pat = await api('/api/memory/patterns');
  check('patterns synthetic-labeled', pat.synthetic === true && pat.patterns.every((p) => p.synthetic === true));
  const agent = await api('/api/time-agent', { method: 'POST', body: JSON.stringify({ question: 'What conflicts were detected?' }) });
  check('agent cited answer', agent.intent === 'conflicts' && agent.citations.length === 6 && /Evidence:/.test(agent.answer));
  const con = await api('/api/conflicts');
  check('conflicts seeded', con.length === 3);
} catch (e) {
  check('backend reachable at ' + API, false, String(e).slice(0, 200));
}

console.log(failures === 0 ? '\nSMOKE PASS' : `\nSMOKE FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);
