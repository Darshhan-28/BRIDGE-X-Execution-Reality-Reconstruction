"""Time Agent: deterministic intent router + tool calling + cited answers.

The LLM (when configured) only summarizes retrieved tool facts; the
deterministic template path always works offline. The LLM never touches
the database and can never trigger writes or schedule changes — it
receives JSON facts and returns prose, nothing more.
"""
import re
from datetime import date, timedelta

from . import time_agent_tools as T
from .ingestion import normalize_date

REPORT_RE = re.compile(r"\b([A-Z]{2,4}-\d{8}-\d{3}|[A-Z]{2,4}-\d{4}-\d{2}-\d{2}-\d{1,3})\b")
ACTIVITY_RE = re.compile(r"\b[A-Z]{3}-[A-Z0-9]{3,4}-\d{3}\b")
LOCATION_RES = [
    ("R-204", re.compile(r"\br[\s-]?204\b", re.I)),
    ("R-210", re.compile(r"\br[\s-]?210\b", re.I)),
    ("B-Block", re.compile(r"\bb[\s-]?block\b", re.I)),
    ("Yard-A", re.compile(r"\byard[\s-]?a\b", re.I)),
    ("S1", re.compile(r"\bs1\b", re.I)),
    ("PH1", re.compile(r"\bph1\b", re.I)),
    ("CR1", re.compile(r"\bcr1\b", re.I)),
]
DATE_RES = [
    re.compile(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4})", re.I),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"),
]

CAPABILITIES = ("I can: list activities started/completed on a date; show delayed activities; "
                "show unmatched reports; explain why a report was linked; show conflicts; "
                "give an activity status. Try: 'What activities started on 6 Sep 2026?', "
                "'Which activities are delayed?', 'Show unmatched reports.', "
                "'Why was DPR-2026-09-18-01 linked to PIP-204-017?', 'What conflicts were detected?'")


def _find_date(q: str) -> str:
    low = q.lower()
    if "yesterday" in low:
        return (date.today() - timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", low):
        return date.today().isoformat()
    for rx in DATE_RES:
        m = rx.search(q)
        if m:
            norm = normalize_date(m.group(1))
            if norm:
                return norm
    return ""


def _find_location(q: str) -> str:
    for name, rx in LOCATION_RES:
        if rx.search(q):
            return name
    return ""


def route(question: str) -> dict:
    """Map a question to {intent, args}. Pure function, no I/O, no LLM."""
    q = (question or "").strip()
    low = q.lower()
    report = REPORT_RE.search(q)
    activity = ACTIVITY_RE.search(q)
    day = _find_date(q)
    loc = _find_location(q)

    if ("conflict" in low or "contradiction" in low or "duplicate" in low) and "why" not in low:
        return {"intent": "conflicts", "args": {}}
    if "unmatch" in low or ("not linked" in low) or ("no match" in low):
        return {"intent": "unmatched", "args": {}}
    if report and ("why" in low or "link" in low or "match" in low or "reject" in low or "explain" in low):
        return {"intent": "explain", "args": {"report_code": report.group(1)}}
    if report:
        return {"intent": "explain", "args": {"report_code": report.group(1)}}
    if activity and ("delay" in low or "why" in low or "status" in low or "behind" in low or "late" in low):
        return {"intent": "status", "args": {"code": activity.group(0)}}
    if activity:
        return {"intent": "status", "args": {"code": activity.group(0)}}
    if "delay" in low or "behind" in low or "overdue" in low or "late" in low:
        return {"intent": "delayed", "args": {"location": loc}}
    if "complet" in low or "finish" in low or re.search(r"\bdone\b", low):
        if day:
            return {"intent": "completed", "args": {"date": day}}
        return {"intent": "unknown", "args": {"hint": "completed on which date?"}}
    if "start" in low or "began" in low or "kicked off" in low or "commenc" in low:
        if day:
            return {"intent": "started", "args": {"date": day}}
        return {"intent": "unknown", "args": {"hint": "started on which date?"}}
    return {"intent": "unknown", "args": {}}


def run_tools(db, routed: dict) -> dict:
    """Execute the routed tool(s) against the database. Only reads."""
    intent, args = routed["intent"], routed.get("args", {})
    if intent == "started":
        return {"started": T.activities_started_on(db, args["date"])}
    if intent == "completed":
        return {"completed": T.activities_completed_on(db, args["date"])}
    if intent == "delayed":
        return {"delayed": T.delayed_activities(db, args.get("location", ""))}
    if intent == "unmatched":
        return {"unmatched": T.unmatched_reports(db)}
    if intent == "explain":
        return {"explain": T.explain_link(db, args["report_code"])}
    if intent == "conflicts":
        return {"conflicts": T.conflicts(db)}
    if intent == "status":
        return {"status": T.activity_status(db, args["code"])}
    return {}


def _template_answer(routed: dict, tools_out: dict) -> str:
    intent = routed["intent"]
    if intent == "started":
        f = tools_out["started"]["facts"]
        names = ", ".join(f"{a['activity_id']} ({a['name'][:45]}…)" for a in f["activities"]) or "none"
        return f"Activities started on {f['date']}: {f['count']} found. {names}."
    if intent == "completed":
        f = tools_out["completed"]["facts"]
        names = ", ".join(f"{a['activity_id']} ({a['name'][:45]}…)" for a in f["activities"]) or "none"
        return f"Activities completed on {f['date']}: {f['count']} found. {names}."
    if intent == "delayed":
        f = tools_out["delayed"]["facts"]
        scope = f" at {f['location']}" if f["location"] != "all" else ""
        top = "; ".join(f"{a['activity_id']} ({a['days_overdue']}d overdue, {a['status']})"
                        for a in f["activities"][:8]) or "none"
        extra = f" Showing top 8 of {f['count']}." if f["count"] > 8 else ""
        return f"Delayed activities{scope}: {f['count']} past planned finish and not complete. {top}.{extra}"
    if intent == "unmatched":
        f = tools_out["unmatched"]["facts"]
        items = "; ".join(f"{r['report_id']} ({r['why']})" for r in f["reports"][:8]) or "none"
        return f"Unmatched field reports: {f['count']}. {items}."
    if intent == "explain":
        f = tools_out["explain"]["facts"]
        if f.get("error"):
            return f"Cannot explain: {f['error']}"
        why = " | ".join(f["candidates"][0]["why"][:4])
        errs = f" Verification errors: {'; '.join(f['verification_errors'])}." if f["verification_errors"] else " Verification passed."
        gate = f.get("gate", {})
        return (f"{f['report_id']} linked to {f['top_activity']} at {f['top_score']} "
                f"(margin {f['margin']}, gate {gate.get('decision', '?')}). Why: {why}.{errs}")
    if intent == "conflicts":
        f = tools_out["conflicts"]["facts"]
        items = "; ".join(f"{c['type']}: {c['evidence_a']} vs {c['evidence_b']} — {c['reason'][:90]}"
                          for c in f["conflicts"]) or "none"
        return f"Detected conflicts: {f['count']}. {items}."
    if intent == "status":
        f = tools_out["status"]["facts"]
        if f.get("error"):
            return f"Cannot answer: {f['error']}"
        a = f["activity"]
        preds = ", ".join(f"{p['activity_id']}={p['status']}" for p in f["predecessors"]) or "none"
        rev = f.get("latest_review") or {}
        rev_s = f" Latest review: {rev.get('report')} -> {rev.get('decision')}." if rev else " No review yet."
        return (f"{a['activity_id']}: {a['name']}. Status {a['status']}, progress {a['progress']}%, "
                f"planned {a['planned']}, actual {a['actual']}. Predecessors: {preds}.{rev_s}")
    hint = routed.get("args", {}).get("hint", "")
    return f"I don't understand that question. {CAPABILITIES}" + (f" ({hint})" if hint else "")


def _compose_with_llm(question: str, routed: dict, tools_out: dict) -> str:
    """Summarize tool facts with OpenRouter. Raises on any failure -> template."""
    import json

    from .config import settings
    from .llm import openrouter as oro

    if not settings.llm_configured:
        raise ValueError("LLM not configured")
    facts = json.dumps({k: v["facts"] for k, v in tools_out.items()})[:6000]
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": ("You answer project questions using ONLY the database facts below. "
                                           "Never invent activities, dates or IDs. Keep every cited ID. "
                                           "If facts show no rows, say so plainly. Return plain text.")},
            {"role": "user", "content": f"Question: {question}\nFacts: {facts}"},
        ],
    }
    last = None
    for _ in (1, 2):
        try:
            resp = oro._post(payload)
        except Exception as e:
            last = e
            continue
        if resp.status_code != 200:
            last = ValueError(f"HTTP {resp.status_code}")
            continue
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            continue
        if content and content.strip():
            return content.strip()
        last = ValueError("empty completion")
    raise ValueError(f"LLM compose failed: {last}")


def answer(question: str, db) -> dict:
    """Full Time Agent turn: route -> tools -> compose -> cited answer."""
    from .config import settings

    routed = route(question)
    tools_out = run_tools(db, routed) if routed["intent"] != "unknown" else {}
    citations = []
    for v in tools_out.values():
        citations += v.get("citations", [])
    composer = "template"
    if tools_out and settings.llm_configured:
        try:
            text = _compose_with_llm(question, routed, tools_out)
            composer = "llm"
        except Exception:
            text = _template_answer(routed, tools_out)
    else:
        text = _template_answer(routed, tools_out)
    if citations:
        text += "\nEvidence: " + "; ".join(f"[{c['type']}] {c['id']}" for c in citations[:12]) + "."
    return {"answer": text, "citations": citations, "intent": routed["intent"],
            "tools_used": list(tools_out), "composer": composer}
