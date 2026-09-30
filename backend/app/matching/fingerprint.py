"""Activity / event fingerprints for contextual schedule linking.

A fingerprint combines structured fields (action, object, discipline,
location, size/tag, WBS) with free-text tokens. Terminology aliases
canonicalize site language (pipe->spool, joint->weld) on both sides so
a mismatch in words does not hide a match in meaning.
"""
from dataclasses import dataclass, field

OBJECT_ALIASES = {
    "pipe": "spool",
    "pipes": "spool",
    "piping": "spool",
    "joint": "weld",
    "joints": "weld",
    "copper": "cable",
    "ct": "cable tray",
    "fdn": "foundation",
    "footing": "foundation",
    "rcc": "foundation",
}


def canon_object(obj: str) -> str:
    return OBJECT_ALIASES.get((obj or "").strip().lower(), (obj or "").strip().lower())


@dataclass
class Fingerprint:
    action: str = ""
    object: str = ""          # canonicalized
    raw_object: str = ""      # as extracted/stored
    discipline: str = ""
    location: str = ""
    size: str = ""
    tag: str = ""
    wbs: str = ""
    name: str = ""
    text: str = ""            # combined free-text for TF-IDF / fuzz
    tokens: list = field(default_factory=list)
    disp_discipline: str = ""  # original casing for WHY display
    disp_location: str = ""


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def fingerprint_from_event(ev) -> Fingerprint:
    action, obj = _norm(ev.action), canon_object(ev.object)
    text = " ".join(p for p in [
        ev.action, ev.action, obj, ev.object, ev.discipline,
        ev.location, ev.size, ev.tag, ev.evidence_text,
    ] if p).lower()
    return Fingerprint(
        action=_norm(ev.action), object=obj, raw_object=_norm(ev.object),
        discipline=_norm(ev.discipline), location=_norm(ev.location),
        size=(ev.size or "").strip(), tag=(ev.tag or "").upper(),
        text=text, tokens=sorted(set(text.split())),
        disp_discipline=(ev.discipline or "").strip() or "?",
        disp_location=(ev.location or "").strip() or "?",
    )


def fingerprint_from_activity(a) -> Fingerprint:
    obj = canon_object(a.object)
    text = " ".join(p for p in [
        a.action, a.action, obj, a.object, a.name,
        a.discipline, a.location, a.size, a.tag, a.wbs_code,
    ] if p).lower()
    return Fingerprint(
        action=_norm(a.action), object=obj, raw_object=_norm(a.object),
        discipline=_norm(a.discipline), location=_norm(a.location),
        size=(a.size or "").strip(), tag=(a.tag or "").upper(),
        wbs=(a.wbs_code or "").strip(), name=a.name or "",
        text=text, tokens=sorted(set(text.split())),
        disp_discipline=(a.discipline or "").strip() or "?",
        disp_location=(a.location or "").strip() or "?",
    )
