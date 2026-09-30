"""Deterministic local field-event parser (offline-first, CPU-only).

Keeps the prototype fully functional with no API key. Normalizes
messy site language (abbreviations, synonyms) to canonical actions,
objects, locations and disciplines.
"""
import re
from datetime import datetime, timedelta

from .base import FieldEvent

# Ordered: first match wins. Each entry: (canonical, [patterns]).
ACTIONS = [
    ("erect", [r"\berec\w*", r"\berection\b", r"\berected\b", r"\berect\b"]),
    ("fit-up", [r"\bfit[\s-]?up\b"]),
    ("weld", [r"\bweld\w*", r"\bwelding\b"]),
    ("test", [r"\bx[\s-]?ray\b", r"\bndt\b", r"\bhydrotest\w*", r"\bleak test\b", r"\bpressure test\w*", r"\btest\w*"]),
    ("paint", [r"\bpaint\w*", r"\bcoating\b", r"\bcoat\w*"]),
    ("insulate", [r"\binsulat\w*"]),
    ("concrete", [r"\bconcret\w*", r"\bpoured\b", r"\bpour\w*", r"\bcast\w*"]),
    ("install", [r"\binstall\w*", r"\binstd\b"]),
    ("lay", [r"\blay\w*", r"\blaying\b"]),
    ("terminate", [r"\bterminat\w*"]),
    ("receive", [r"\breceiv\w*"]),
    ("transport", [r"\btransport\w*", r"\bshifted\b", r"\bdeliver\w*"]),
    ("excavate", [r"\bexcavat\w*"]),
    ("rebar", [r"\brebar\b", r"\breinforcement\b"]),
    ("cure", [r"\bcuring\b", r"\bcure\b", r"\bformwork\b"]),
    ("backfill", [r"\bbackfill\w*"]),
    ("grout", [r"\bgrout\w*"]),
    ("align", [r"\balign\w*", r"\btrueness\b"]),
    ("check", [r"\bloop[\s-]?check\w*", r"\bcheck\w*"]),
    ("calibrate", [r"\bcalibrat\w*", r"\bcal\.?\b"]),
    ("wire", [r"\bwir\w*"]),
    ("flush", [r"\bflush\w*"]),
    ("construct", [r"\bconstruct\w*"]),
    ("prepare", [r"\bprep\b", r"\bprepar\w*"]),
    ("deploy", [r"\bdeploy\w*"]),
    ("extend", [r"\bextend\w*", r"\bextension\b"]),
    ("fabricate", [r"\bfabricat\w*", r"\bfab\.?\b"]),
]

OBJECTS = [
    ("spool", [r"\bsp\.?\b", r"\bspool\w*"]),
    ("weld", [r"\bweld\w*", r"\bjoint\w*"]),
    ("cable tray", [r"\bct\b", r"\bcable tray\b"]),
    ("cable", [r"\bcabl\w*", r"\bcopper\b"]),
    ("anchor bolt", [r"\banchor bolt\w*"]),
    ("air header", [r"\bair header\b"]),
    ("foundation", [r"\bfdn\b", r"\bfoundation\w*", r"\bfooting\b"]),
    ("transmitter", [r"\btransmitter\w*", r"\bpt[-\s]?\d+\b"]),
    ("valve", [r"\bvalve\w*", r"\bcv[-\s]?\d+\b"]),
    ("tubing", [r"\btub\w*"]),
    ("loop", [r"\bloop\b"]),
    ("panel", [r"\bpanel\b", r"\bdcs\b"]),
    ("transformer", [r"\btransformer\w*"]),
    ("busbar", [r"\bbusbar\b", r"\bbus bar\b"]),
    ("lighting", [r"\blight\w*"]),
    ("earthing", [r"\bearth\w*"]),
    ("lighting", [r"\blight\w*"]),
    ("pump", [r"\bpump\w*", r"\bp[-\s]?\d{3,4}[a-z]?\b"]),
    ("compressor", [r"\bcompressor\w*"]),
    ("lube oil", [r"\blube oil\b"]),
    ("line", [r"\bline\b", r"\bpipeline\b"]),
    ("pipe", [r"\bpipe\b"]),
    ("road", [r"\broad\w*", r"\bdrain\w*"]),
    ("plinth", [r"\bplinth\b"]),
    ("pile", [r"\bpil\w*"]),
    ("support", [r"\bsupport\w*"]),
    ("crane", [r"\bcrane\b"]),
    ("scada", [r"\bscada\b"]),
    ("substation", [r"\bsubstation\b"]),
    ("building", [r"\bbuilding\b"]),
]

LOCATIONS = [
    ("R-204", [r"\br[\s-]?204\b", r"\brack[\s-]?204\b", r"\brack r[\s-]?204\b"]),
    ("R-210", [r"\br[\s-]?210\b", r"\brack[\s-]?210\b"]),
    ("Yard-A", [r"\byard[\s-]?a\b"]),
    ("B-Block", [r"\bb[\s-]?block\b"]),
    ("S1", [r"\bs1\b", r"\bsubstation s1\b", r"\bsubstation\b"]),
    ("PH1", [r"\bph1\b", r"\bpump[\s-]?house\b"]),
    ("CR1", [r"\bcr1\b", r"\bcontrol[\s-]?room\b"]),
    ("Guest-House", [r"\bguest[\s-]?house\b"]),
    ("Perimeter", [r"\bperimeter\b", r"\bboundary\b"]),
    ("Canteen", [r"\bcanteen\b"]),
]

DISCIPLINES = [
    ("Piping", [r"\bpip\w*\b"]),
    ("Civil", [r"\bcivil\b"]),
    ("Electrical", [r"\belectr\w*", r"\bcopper\b"]),
    ("Mechanical", [r"\bmechan\w*"]),
    ("Instrumentation", [r"\binstrum\w*", r"\bloops?\b", r"\bdcs\b", r"\bscada\b"]),
]

SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(?:in\b|in\.|inch(?:es)?|\"|”)", re.I)
TAG_RE = re.compile(r"\b([A-Z]{1,4}[-\s]?\d{3,4}[A-Z]?)\b")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(?:%|pct|percent)", re.I)
DATE_RES = [
    re.compile(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4})", re.I),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"),
]

COMPLETION_RES = [r"\bcomplet\w*", r"\bdone\b", r"\bfinish\w*", r"\berected\b", r"\bachiev\w*"]
PROGRESS_RES = [r"\bpercent\b", r"\bpct\b", r"%\b", r"\bhalf\b", r"\bhalfway\b", r"\bpartial\b", r"\bin progress\b"]
START_RES = [r"\bstart\w*", r"\bbeg[au]n\b", r"\bkicked off\b", r"\bcommenced\b"]
NEG_RES = [r"\bnot yet\b", r"\bpending\b", r"\bnot started\b", r"\byet to\b"]


def _first_match(rules: list[tuple[str, list[str]]], text: str) -> str:
    for canon, pats in rules:
        for p in pats:
            if re.search(p, text, re.I):
                return canon
    return ""


def _resolve_date(text: str, report_date: str) -> tuple[str, str | None]:
    """Return (event_date, warning). Handles explicit dates + yesterday/today."""
    for rx in DATE_RES:
        m = rx.search(text)
        if m:
            from ..ingestion import normalize_date

            norm = normalize_date(m.group(1))
            if norm:
                return norm, None
            return "", f"Unparseable date mention '{m.group(1)}'."
    low = text.lower()
    if "yesterday" in low and report_date:
        try:
            d = datetime.strptime(report_date, "%Y-%m-%d").date() - timedelta(days=1)
            return d.isoformat(), None
        except ValueError:
            return "", f"Could not resolve 'yesterday' against report_date '{report_date}'."
    if "today" in low and report_date:
        return report_date, None
    return report_date, None


def parse_event_fallback(
    text: str,
    report_id: str = "",
    report_date: str = "",
    discipline_hint: str = "",
    location_hint: str = "",
) -> FieldEvent:
    raw = (text or "").strip()
    low = raw.lower()
    warnings: list[str] = []

    action = _first_match(ACTIONS, low)
    obj = _first_match(OBJECTS, low)
    location = _first_match(LOCATIONS, low) or (location_hint or "")
    discipline = _first_match(DISCIPLINES, low) or (discipline_hint or "")

    # "pipe erection" should read as spool-class work only when spool tokens exist;
    # otherwise keep the literal object so matching sees the mismatch honestly.
    size_m = SIZE_RE.search(raw)
    size = f'{size_m.group(1)}"' if size_m else ""
    tag_m = TAG_RE.search(raw)
    tag = tag_m.group(1).upper().replace(" ", "") if tag_m else ""

    pct_m = PCT_RE.search(raw)
    progress = float(pct_m.group(1)) if pct_m else None
    if progress is None and re.search(r"\bhalf\b|\bhalfway\b", low):
        progress = 50.0

    negated = any(re.search(p, low) for p in NEG_RES)
    if negated:
        event_type = "status"
        progress = 0.0 if progress is None else progress
    elif progress is not None:
        event_type = "completion" if progress >= 100 else "progress"
    elif any(re.search(p, low) for p in COMPLETION_RES):
        event_type = "completion"
        progress = 100.0
    elif any(re.search(p, low) for p in START_RES):
        event_type = "start"
    elif any(re.search(p, low) for p in PROGRESS_RES):
        event_type = "progress"
    else:
        event_type = "unknown"
        warnings.append("No clear status signal; event_type set to 'unknown'.")

    event_date, date_warn = _resolve_date(raw, report_date)
    if date_warn:
        warnings.append(date_warn)
    if not event_date:
        warnings.append("No event date found; fell back to report_date." if report_date else "No event date found.")
        event_date = report_date

    if not action:
        warnings.append("No action detected.")
    if not obj:
        warnings.append("No object detected; match may be ambiguous.")
    if not location:
        warnings.append("No location detected.")
    if not discipline:
        warnings.append("No discipline detected.")

    return FieldEvent(
        event_type=event_type,
        action=action,
        object=obj,
        size=size,
        tag=tag,
        location=location,
        discipline=discipline,
        event_date=event_date,
        progress_pct=progress,
        evidence_text=raw,
        report_id=report_id,
        extractor="fallback",
        warnings=warnings,
    )
