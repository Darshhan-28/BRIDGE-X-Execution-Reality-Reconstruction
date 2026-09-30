"""Phase 3 tests: text / CSV / XLSX / text-PDF / scanned-PDF ingestion."""
import io

import fitz
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from seed.synthetic_project import run_seed

client = TestClient(app)


def _reset():
    run_seed()


def test_text_report_preserved():
    _reset()
    raw = "24 inch spool erection completed at R-204 on 18 Sep 2026."
    r = client.post("/api/reports", json={"raw_text": raw, "report_date": "2026-09-18"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["raw_text"] == raw  # verbatim preservation
    assert body["report_date"] == "2026-09-18"
    assert body["linked_activity_code"] is None


def test_text_report_rejects_empty():
    _reset()
    assert client.post("/api/reports", json={"raw_text": "   "}).status_code == 422
    assert client.post("/api/reports", json={"raw_text": ""}).status_code == 422


def test_csv_flexible_columns():
    _reset()
    csv = (
        "Day,Disc,Site,Narration,Contractor\n"
        "18 Sep 2026,Piping,R-204,24 inch spool erected,ABC Infra\n"
        "19 Sep 2026,Civil,B-Block,Foundation curing in progress,XYZ Ltd\n"
    )
    r = client.post(
        "/api/reports/analyze",
        files={"file": ("dpr.csv", csv.encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inserted"] == 2
    assert body["ocr_required"] is False
    recs = client.get("/api/reports", params={"category": "unclassified"}).json()
    assert len(recs) == 2
    first = next(x for x in recs if "spool" in x["raw_text"])
    assert first["discipline"] == "Piping"
    assert first["location"] == "R-204"
    assert first["report_date"] == "2026-09-18"
    assert "ABC Infra" in first["raw_text"]  # metadata preserved in raw text
    assert "ABC Infra" in first["meta"]  # ... and in structured meta


def test_xlsx_ingestion():
    _reset()
    df = pd.DataFrame([
        {"date": "2026-09-20", "discipline": "Electrical", "location": "S1",
         "description": "Busbar installation completed", "status": "done"},
    ])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    r = client.post(
        "/api/reports/analyze",
        files={"file": ("dpr.xlsx", buf.read(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 1
    recs = client.get("/api/reports", params={"category": "unclassified"}).json()
    assert recs[0]["report_date"] == "2026-09-20"
    assert "Busbar" in recs[0]["raw_text"]


def _make_pdf(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "\n".join(lines))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_text_pdf_ingestion():
    _reset()
    pdf = _make_pdf([
        "Daily Progress Report 18 Sep 2026",
        "24 inch spool erection completed at R-204.",
        "Contractor: ABC Infra. Discipline: Piping.",
    ])
    r = client.post("/api/reports/analyze", files={"file": ("dpr.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inserted"] == 1
    recs = client.get("/api/reports", params={"category": "unclassified"}).json()
    assert "spool erection" in recs[0]["raw_text"]
    assert recs[0]["source"] == "pdf"


def test_scanned_pdf_flagged_not_parsed():
    _reset()
    doc = fitz.open()
    doc.new_page()  # blank page: no extractable text
    buf = io.BytesIO()
    doc.save(buf)
    r = client.post("/api/reports/analyze", files={"file": ("scan.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inserted"] == 0
    assert body["ocr_required"] is True
    assert any("OCR required" in w for w in body["warnings"])


def test_unsupported_file_rejected():
    _reset()
    r = client.post("/api/reports/analyze", files={"file": ("notes.docx", b"junk", "application/octet-stream")})
    assert r.status_code == 400
