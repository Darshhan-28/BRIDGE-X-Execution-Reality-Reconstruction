import { useState } from 'react';
import { api } from '../api';
import type { AgentReply } from '../types';
import { Badge, ErrorBox, PipelineStrip } from '../components';

const EXAMPLES = [
  'What activities started on 6 Sep 2026?',
  'Which activities are delayed?',
  'Show unmatched field reports.',
  'Why was DPR-2026-09-18-01 linked to PIP-204-017?',
  'What conflicts were detected?',
  'Why is PIP-204-019 delayed?',
];

interface Msg { role: 'q' | 'a'; text: string; reply?: AgentReply }

export default function Agent() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lastQ, setLastQ] = useState('');

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true); setError(''); setLastQ(text);
    setMsgs((m) => [...m, { role: 'q', text }]);
    setQ('');
    try {
      const reply = await api.agent(text);
      setMsgs((m) => [...m, { role: 'a', text: reply.answer, reply }]);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <h2>Time Agent</h2>
      <PipelineStrip active="UNDERSTOOD" />
      <p className="mut">Database-grounded answers with evidence citations. The agent reads the database only — it never writes.</p>
      <div className="btnrow">
        {EXAMPLES.map((e) => (
          <button type="button" key={e} className="chip" disabled={busy} onClick={() => ask(e)}>{e}</button>
        ))}
      </div>
      <div className="chat">
        {msgs.length === 0 && <p className="mut">Ask a question, or tap an example above.</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <p style={{ whiteSpace: 'pre-wrap' }}>{m.text}</p>
            {m.reply && (
              <div className="cites">
                <Badge tone="mut">{m.reply.intent}</Badge>
                <Badge tone="mut">via {m.reply.composer}</Badge>
                {m.reply.citations.slice(0, 12).map((c, j) => (
                  <Badge key={j} tone={c.type === 'report' ? 'warn' : 'ok'}>{c.type}: {c.id}</Badge>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="mut">Thinking…</p>}
      </div>
      {error && <ErrorBox error={error} retry={lastQ ? () => ask(lastQ) : undefined} />}
      <div className="formrow">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') ask(q); }}
          placeholder="Ask about starts, delays, links, conflicts…" />
        <button type="button" disabled={busy || !q.trim()} onClick={() => ask(q)}>Ask</button>
      </div>
    </div>
  );
}
