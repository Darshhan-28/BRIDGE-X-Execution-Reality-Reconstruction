"""REAL-DATA phase: curated public Oil India knowledge seed.

Every SOURCE below was fetched first-hand (see local_file + retrieved_at).
Every TERM carries a verbatim snippet observed in that source document.
Nothing here is a DPR, a schedule node, or progress — context only.

Excluded (documented in docs/OIL_PUBLIC_DATA.md, NOT integrated):
- PNGRB IGGL authorization PDF: scanned images, zero extractable chars,
  excluded per the no-OCR constraint.
- Search-result snippets (tender titles seen only in search excerpts):
  provenance too weak; only terms from directly fetched files are stored.

Idempotent: upserts by source_id / (source_id, term, category).
run_seed() never wipes these tables; use load_oil_knowledge() explicitly.
"""
import hashlib
import json
import os

RETRIEVED_AT = "2026-09-22"

SOURCES = [
    {
        "source_id": "OIL-MIDSTREAM-20260325",
        "title": "Midstream | Oil India Limited (Pipeline - The Energy Highway)",
        "publisher": "Oil India Limited",
        "source_url": "https://www.oil-india.com/integrated-energy-company/midstream",
        "publication_date": "2026-03-25",
        "retrieved_at": RETRIEVED_AT,
        "document_type": "official webpage",
        "local_file": "backend/data/oil_public/oil_midstream_page.html",
        "notes": "Page header states Last Updated 25/03/2026. Pipeline portfolio, rehabilitation projects, locations.",
    },
    {
        "source_id": "OIL-INVESTOR-TRANSCRIPT-20260529",
        "title": "Transcript of Analysts' and Investors' Meet on 25th May, 2026",
        "publisher": "Oil India Limited",
        "source_url": "https://www.oil-india.com/files/investor_services_documents/2a520951_8bd3_4612_92b2_5e1b1ca8af5b.pdf",
        "publication_date": "2026-05-29",
        "retrieved_at": RETRIEVED_AT,
        "document_type": "official investor transcript (PDF, 30 pages)",
        "local_file": "backend/data/oil_public/oil_investor_meet_transcript_2026-05-29.pdf",
        "notes": "Forwarded to NSE/BSE under SEBI LODR; project execution vocabulary (completion, ROU, commissioning).",
    },
    {
        "source_id": "OIL-NIT-CDG5545P24",
        "title": "E-Tender No. CDG5545P24 Forwarding Letter (Charter Hire drilling rigs)",
        "publisher": "Oil India Limited, Contracts Department, Duliajan",
        "source_url": "https://www.oil-india.com/files/oldtender/global/NIT_CDG5545P24.pdf",
        "publication_date": "2024-02",
        "retrieved_at": RETRIEVED_AT,
        "document_type": "official tender document (PDF, 385 pages; curated from first 60)",
        "local_file": "backend/data/oil_public/oil_nit_CDG5545P24.pdf",
        "notes": "IFB for charter hire of 2000 HP drilling rig package; procurement + rig terminology. Bid closing 29.02.2024.",
    },
    {
        "source_id": "OIL-TENDER-LIST-202609",
        "title": "OIL National Tenders list snapshot (tender-list/63)",
        "publisher": "Oil India Limited",
        "source_url": "https://www.oil-india.com/tender-list/63",
        "publication_date": "",
        "retrieved_at": RETRIEVED_AT,
        "document_type": "official tender listing snapshot (live page, tenders dated Aug-Oct 2026)",
        "local_file": "backend/data/oil_public/oil_tender_list_national.html",
        "notes": "Live listing snapshot; work descriptions for civil/rig-site works. Titles change over time.",
    },
]

# (source_id, term, category, context_snippet, section_ref, extra)
TERMS = [
    ("OIL-MIDSTREAM-20260325", "trunk pipeline", "equipment",
     "OIL's 1247 Km fully automated trunk pipeline with a capacity of 9.65 MMTPA",
     "Pipeline - The Energy Highway", {"measurement": "1247 Km, 9.65 MMTPA"}),
    ("OIL-MIDSTREAM-20260325", "pumping station", "equipment",
     "The network of 11 pumping stations and 17 repeater stations",
     "Pipeline - The Energy Highway", {"count": "11 pumping, 17 repeater"}),
    ("OIL-MIDSTREAM-20260325", "repeater station", "equipment",
     "The network of 11 pumping stations and 17 repeater stations",
     "Pipeline - The Energy Highway", {}),
    ("OIL-MIDSTREAM-20260325", "prime mover engines", "equipment",
     "running the crude oil fuelled prime mover engines & the pumps in its originally established Pump Stations for over 200,000 hours",
     "Pipeline - The Energy Highway", {}),
    ("OIL-MIDSTREAM-20260325", "cathodic protection system", "equipment",
     "which includes complete refurbishment of pipeline coating, re-designing of cathodic protection system, Mitigation of shorted cased crossings",
     "Pipeline rehabilitation works", {}),
    ("OIL-MIDSTREAM-20260325", "river crossings", "construction",
     "the crude oil pipeline traverses 78 river crossings through the states of Assam, West Bengal and Bihar",
     "Pipeline - The Energy Highway", {"count": "78 crossings"}),
    ("OIL-MIDSTREAM-20260325", "micro-tunnelling", "construction",
     "Micro-tunnelling Phase II Project has been initiated to execute trenchless crossings",
     "Micro-tunnelling Project - Phase II (River Crossings)", {}),
    ("OIL-MIDSTREAM-20260325", "coating refurbishment", "action",
     "Phase I of Pipeline Rehabilitation Project, which covered 593 km of coating refurbishment",
     "Pipeline rehabilitation works", {"quantity": "593 km"}),
    ("OIL-MIDSTREAM-20260325", "pigging stations", "equipment",
     "upgrading existing pigging stations to intermediate pump stations at Sekoni, Guwahati, Bongaigaon and Madarihat",
     "NSPL Augmentation works", {}),
    ("OIL-MIDSTREAM-20260325", "OFC based communication network", "equipment",
     "equipped with new cathodic protection system and OFC based communication network",
     "Pipeline replacement works", {}),
    ("OIL-MIDSTREAM-20260325", "MMTPA", "measurement",
     "fully automated trunk pipeline with a capacity of 9.65 MMTPA",
     "Pipeline - The Energy Highway", {"note": "million metric tonnes per annum (unit as used)"}),
    ("OIL-MIDSTREAM-20260325", "NSPL", "abbreviation",
     "Numaligarh-Siliguri Product Pipeline (NSPL) Augmentation from existing 1.72 MMTPA to 5.5 MMTPA",
     "Projects Underway", {"expansion": "Numaligarh-Siliguri Product Pipeline"}),
    ("OIL-MIDSTREAM-20260325", "DNPL", "abbreviation",
     "The Duliajan - Numaligarh Gas Pipeline (DNPL) where OIL has 23% equity stake",
     "Pipeline portfolio", {"expansion": "Duliajan-Numaligarh Gas Pipeline"}),
    ("OIL-MIDSTREAM-20260325", "Duliajan", "location",
     "The Duliajan - Numaligarh Gas Pipeline (DNPL)",
     "Pipeline portfolio", {}),
    ("OIL-MIDSTREAM-20260325", "Numaligarh", "location",
     "The Duliajan - Numaligarh Gas Pipeline (DNPL)",
     "Pipeline portfolio", {}),
    ("OIL-MIDSTREAM-20260325", "Guwahati", "location",
     "upgrading existing pigging stations to intermediate pump stations at Sekoni, Guwahati, Bongaigaon and Madarihat",
     "NSPL Augmentation works", {}),
    ("OIL-MIDSTREAM-20260325", "Bongaigaon", "location",
     "transporting Imported crude from Barauni to Bongaigaon",
     "Pipeline - The Energy Highway", {}),
    ("OIL-MIDSTREAM-20260325", "Barauni", "location",
     "transporting Imported crude from Barauni to Bongaigaon",
     "Pipeline - The Energy Highway", {}),
    ("OIL-MIDSTREAM-20260325", "Siliguri", "location",
     "Numaligarh-Siliguri Product Pipeline (NSPL)",
     "Projects Underway", {}),
    ("OIL-MIDSTREAM-20260325", "augmentation", "project",
     "NSPL Augmentation from existing 1.72 MMTPA to 5.5 MMTPA, 2021-2024 (ongoing)",
     "Projects Underway", {}),
    ("OIL-MIDSTREAM-20260325", "commissioned", "milestone",
     "It was commissioned on 27th April 2024",
     "Pipeline replacement works", {"date": "2024-04-27"}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "mechanical completion", "milestone",
     "Mechanical completion was achieved on 12th of October'2025",
     "Investors' and Analysts' Meet transcript", {}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "physical completion", "milestone",
     "we have achieved 92% physical completion",
     "Investors' and Analysts' Meet transcript", {"value": "92%"}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "ROU acquired", "execution",
     "we have achieved 92% physical completion and 99% of ROU acquired",
     "Investors' and Analysts' Meet transcript", {"note": "ROU = Right of Use (term as used)"}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "commissioning", "action",
     "By March 2027, the entire refinery 9 million ton will be commissioned",
     "Investors' and Analysts' Meet transcript", {}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "capacity expansion", "project",
     "our NRL refinery expansion from 3 to 9 MMTPA is all well in underway",
     "Investors' and Analysts' Meet transcript", {}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "MMSCMD", "measurement",
     "expansion from 1.2 to 2.5 MMSCMD",
     "Investors' and Analysts' Meet transcript", {"note": "gas volume unit as used"}),
    ("OIL-INVESTOR-TRANSCRIPT-20260529", "shutdown", "execution",
     "NRL we are unable to take a shutdown of 7 days. Once we take a shutdown of 7 days DNPL will get commissioned",
     "Investors' and Analysts' Meet transcript", {}),
    ("OIL-NIT-CDG5545P24", "Charter Hire", "procurement",
     "Charter Hire of 03 (Three) Numbers of 2000 HP [Minimum] Drilling Rig Package",
     "FORWARDING LETTER", {}),
    ("OIL-NIT-CDG5545P24", "Drilling Rig Package", "equipment",
     "Charter Hire of 03 (Three) Numbers of 2000 HP [Minimum] Drilling Rig Package",
     "FORWARDING LETTER", {}),
    ("OIL-NIT-CDG5545P24", "2000 HP", "specification",
     "2000 HP [Minimum] Drilling Rig Package",
     "FORWARDING LETTER", {}),
    ("OIL-NIT-CDG5545P24", "Mobilization Time", "schedule-like",
     "Bidder must confirm to mobilize the Drilling Rig within 120 days from the date of issue of Mobilization Notice",
     "FORWARDING LETTER", {"note": "tender mobilization term, not a project actual"}),
    ("OIL-NIT-CDG5545P24", "Operating Day Rate", "procurement",
     "Payment towards Standby Day Rate shall be 90% (ninety percent) of the Operating Day Rate",
     "Bid Document pricing terms", {}),
    ("OIL-NIT-CDG5545P24", "Draw-works", "equipment",
     "of the Draw-works of offered rig should be minimum 2000 HP",
     "PART-2: BEC/BRC", {}),
    ("OIL-NIT-CDG5545P24", "mast and sub-structure", "equipment",
     "self-elevating type mast and sub-structure (conforming to API specification 4F)",
     "PART-2: BEC/BRC", {}),
    ("OIL-NIT-CDG5545P24", "IFB", "abbreviation",
     "IFB No. CDG5545P24 for 'Charter Hire of 03 Numbers of 2000 HP Drilling Rig Package'",
     "FORWARDING LETTER", {"note": "tender identifier prefix as used; expansion not claimed"}),
    ("OIL-NIT-CDG5545P24", "ICB", "abbreviation",
     "OIL invites International Competitive Bids (ICB) from competent and experienced Contractors",
     "FORWARDING LETTER", {"expansion": "International Competitive Bids"}),
    ("OIL-NIT-CDG5545P24", "Bid Security", "procurement",
     "Bid Security Amount : Bidders quoting for Charter Hire of 01 (One) rig: Rs. 4.38 Crore",
     "FORWARDING LETTER", {}),
    ("OIL-NIT-CDG5545P24", "Demobilization Charges", "procurement",
     "Demobilization Charges for each rig package should not be less than 2% of the estimated total Contract value",
     "Bid Document pricing terms", {}),
    ("OIL-NIT-CDG5545P24", "Duliajan Assam headquarters", "location",
     "premier oil Company engaged in exploration, production and transportation of crude oil & natural gas with its Headquarters at Duliajan, Assam",
     "FORWARDING LETTER", {}),
    ("OIL-TENDER-LIST-202609", "Well plinth", "construction",
     "Construction of Well plinth including perimeter dwarf wall of approximate length 750.0 m",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "CC/RCC Foundation", "construction",
     "Construction of CC/RCC Foundation to suit E-2000, VFD Rig outfit",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "PEB Roof", "construction",
     "Engineering, Procurement, Construction and Commissioning of PEB Roof over Rig Building",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "EOT Crane", "equipment",
     "EOT Crane facility having 50 MT Primary Hoist",
     "National Tenders list snapshot", {"spec": "50 MT primary hoist"}),
    ("OIL-TENDER-LIST-202609", "VFD Rig", "equipment",
     "Construction of CC/RCC Foundation to suit E-2000, VFD Rig outfit at Tengakhat & Chabua",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "Tengakhat", "location",
     "any other drilling location at Tengakhat & Chabua",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "Chabua", "location",
     "any other drilling location at Tengakhat & Chabua",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "Dibrugarh district", "location",
     "any area under Central Field-West in Dibrugarh district",
     "National Tenders list snapshot", {}),
    ("OIL-TENDER-LIST-202609", "Engineering Procurement Construction and Commissioning", "phrase",
     "Engineering, Procurement, Construction and Commissioning of PEB Roof over Rig Building",
     "National Tenders list snapshot", {}),
]


def _checksum(local_file: str) -> str:
    import hashlib

    for base in ("backend/", ""):
        path = base + local_file
        if os.path.exists(path):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return "sha256:" + h.hexdigest()
    return ""


def load_oil_knowledge(db=None) -> dict:
    """Idempotent load of curated public OIL knowledge (upsert by IDs)."""
    from app.db import Base, SessionLocal, engine
    from app.models import DomainTerm, SourceDocument

    close = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close = True
    try:
        n_src = n_terms = 0
        for s in SOURCES:
            row = db.query(SourceDocument).filter(
                SourceDocument.source_id == s["source_id"]).first()
            if not row:
                row = SourceDocument(source_type="REAL_PUBLIC", **{
                    k: v for k, v in s.items() if k != "source_id"},
                    source_id=s["source_id"])
                row.checksum = _checksum(s["local_file"])
                db.add(row)
                n_src += 1
            elif not row.checksum:
                row.checksum = _checksum(s["local_file"])
        for sid, term, cat, snippet, section, extra in TERMS:
            hit = db.query(DomainTerm).filter(
                DomainTerm.source_id == sid, DomainTerm.term == term,
                DomainTerm.category == cat).first()
            if not hit:
                db.add(DomainTerm(source_id=sid, term=term, category=cat,
                                  context_snippet=snippet, section_ref=section,
                                  extra_json=json.dumps(extra or {})))
                n_terms += 1
        db.commit()
        return {"sources": db.query(SourceDocument).count(),
                "new_sources": n_src,
                "terms": db.query(DomainTerm).count(),
                "new_terms": n_terms}
    finally:
        if close:
            db.close()


if __name__ == "__main__":
    print(load_oil_knowledge())
