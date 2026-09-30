"""BRIDGE-X Phase 3 field ingestion service.

Text / CSV / XLSX / text-PDF ingestion. No OCR: scanned PDFs are
explicitly flagged "Prototype / OCR required" and never silently parsed.
Original raw text + metadata are always preserved on the FieldReport.
"""
import io
import json
from datetime import date, datetime

import fitz  # PyMuPDF
import pandas as pd
from sqlalchemy.orm import Session

from .models import FieldReport

# Minimum extractable characters for a PDF to count as a text PDF.
MIN_TEXT_CHARS = 50

OCR_FLAG = "Prototype / OCR required — scanned PDF with no extractable text."

# Flexible header -> canonical field mapping (lowercased, stripped).
COLUMN_ALIASES = {
    "date": "report_date",
    "report_date": "report_date",
    "reportdate": "report_date",
    "day": "report_date",
    "discipline": "discipline",
    "disc": "discipline",
    "dept": "discipline",
    "location": "location",
    "loc": "location",
    "site": "location",
    "area": "location",
    "description": "description",
    "details": "description",
    "remarks": "description",
    "report": "description",
    "text": "description",
    "narration": "description",
    "activity": "description",
    "status": "status",
    "progress": "status",
    "contractor": "contractor",
    "vendor": "contractor",
    "agency": "contractor",
}

_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y",
    "%Y.%m.%d", "%d.%m.%Y",
)


def normalize_date(value) -> str | None:
    """Return YYYY-MM-DD or None if unparseable. Never raises."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        from dateutil.parser import parse as _parse

        return _parse(s, dayfirst=True).date().isoformat()
    except Exception:
        return None


def _norm_header(h: str) -> str:
    return str(h).strip().lower().replace(" ", "_")


def map_columns(headers: list[str]) -> dict[int, str]:
    """Map column index -> canonical field name."""
    mapping: dict[int, str] = {}
    for i, h in enumerate(headers):
        mapping[i] = COLUMN_ALIASES.get(_norm_header(h), f"extra_{i}")
    return mapping


def parse_tabular(df: pd.DataFrame, filename: str) -> tuple[list[dict], list[str]]:
    """Parse a CSV/XLSX frame into candidate report dicts + warnings."""
    warnings: list[str] = []
    df = df.dropna(how="all")
    if df.empty:
        return [], [f"{filename}: no data rows found."]
    headers = [str(c) for c in df.columns]
    mapping = map_columns(headers)
    canonical = {mapping[i] for i in mapping}
    if "description" not in canonical and not any(c.startswith("extra_") for c in canonical):
        warnings.append(f"{filename}: no description-like column found; tried: {headers}.")
    parsed: list[dict] = []
    for idx, row in df.iterrows():
        cells = [(mapping[i], row.iloc[i]) for i in range(len(headers))]
        vals = {k: ("" if pd.isna(v) else str(v).strip()) for k, v in cells}
        desc = vals.pop("description", "")
        rdate = normalize_date(vals.pop("report_date", ""))
        disc = vals.pop("discipline", "")
        loc = vals.pop("location", "")
        status = vals.pop("status", "")
        contractor = vals.pop("contractor", "")
        extras = {k: v for k, v in vals.items() if v}
        parts = [p for p in [desc, status, contractor] if p]
        if not parts:
            parts = [f"{h}: {vals.get(f'extra_{i}', '')}" for i, h in enumerate(headers)]
            parts = [p for p in parts if p and not p.endswith(": ")]
        raw_text = " | ".join(parts).strip()
        if not raw_text:
            warnings.append(f"{filename} row {idx}: empty row skipped.")
            continue
        meta = {"filename": filename, "row": int(idx)}
        if contractor:
            meta["contractor"] = contractor
        if status:
            meta["status_text"] = status
        if extras:
            meta["extra_columns"] = extras
        if not rdate:
            warnings.append(f"{filename} row {idx}: date missing/unparseable, using today.")
            rdate = date.today().isoformat()
        parsed.append({
            "raw_text": raw_text,
            "discipline": disc,
            "location": loc,
            "report_date": rdate,
            "meta": meta,
        })
    return parsed, warnings


def extract_pdf(data: bytes, filename: str) -> tuple[str, dict, list[str]]:
    """Extract text from a PDF. Returns (text, meta, warnings).

    Text-less PDFs are NOT guessed: they return empty text with
    ocr_required=True so the caller flags them explicitly.
    """
    warnings: list[str] = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        return "", {"filename": filename, "error": str(e)}, [f"{filename}: not a readable PDF ({e})."]
    pages = doc.page_count
    chunks = []
    for page in doc:
        chunks.append(page.get_text("text"))
    text = "\n".join(chunks).strip()
    # Normalize whitespace, drop control chars but keep it readable.
    text = "\n".join(line.strip() for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line).strip()
    meta = {"filename": filename, "pages": pages, "chars": len(text)}
    if len(text) < MIN_TEXT_CHARS:
        meta["ocr_required"] = True
        warnings.append(f"{filename}: {OCR_FLAG} ({pages} page(s), {len(text)} chars).")
        return "", meta, warnings
    return text, meta, warnings


def generate_report_code(db: Session, report_date: str, prefix: str = "ING") -> str:
    base = f"{prefix}-{report_date.replace('-', '')}"
    n = db.query(FieldReport).filter(FieldReport.report_code.like(f"{base}%")).count()
    code = f"{base}-{n + 1:03d}"
    while db.query(FieldReport).filter(FieldReport.report_code == code).first():
        n += 1
        code = f"{base}-{n + 1:03d}"
    return code


def create_report(
    db: Session,
    raw_text: str,
    source: str,
    report_date: str,
    discipline: str = "",
    location: str = "",
    category: str = "unclassified",
    meta: dict | None = None,
    source_type: str = "USER_PROVIDED",
) -> FieldReport:
    code = generate_report_code(db, report_date, "ING" if source != "text" else "TXT")
    rec = FieldReport(
        report_code=code,
        raw_text=raw_text,
        source=source,
        discipline=discipline or "",
        location=location or "",
        report_date=report_date,
        category=category,
        linked_activity_code=None,
        source_type=source_type,
        meta=json.dumps(meta or {}),
    )
    db.add(rec)
    db.flush()
    return rec


def read_upload(filename: str, data: bytes) -> tuple[str, bytes]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls", "pdf", "txt"):
        raise ValueError(f"Unsupported file type '.{ext}'. Use CSV, XLSX, PDF or TXT.")
    return ext, data


def dataframe_from_upload(ext: str, data: bytes) -> pd.DataFrame:
    if ext == "csv":
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(data), encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.BytesIO(data), encoding="utf-8", encoding_errors="replace")
    return pd.read_excel(io.BytesIO(data))
