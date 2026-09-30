"""BRIDGE-X Phase 2 synthetic project seed.

Synthetic demonstration data — not real Oil India data.

Covers: 1 project, 12 WBS nodes, 55 activities, FS relationships,
35 field reports across all required categories, execution history,
seeded conflicts. Idempotent: safe to re-run.
"""
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import (
    Activity,
    ActivityRelationship,
    AuditEvent,
    Conflict,
    ExecutionHistory,
    ExtractedEvent,
    FieldReport,
    MatchCandidate,
    Project,
    ProjectVocabulary,
    ReviewDecision,
    ScheduleUpdate,
    VerificationResult,
    WbsNode,
)

PROJECT = {"code": "BRX-DEMO-01", "name": "BRIDGE-X Demo Refinery Upgrade (Synthetic)"}

WBS_NODES = [
    # L5 parents
    {"code": "WBS-PIP-0", "name": "Piping Works (L5)", "level": 5, "parent_code": None},
    {"code": "WBS-CIV-0", "name": "Civil Works (L5)", "level": 5, "parent_code": None},
    {"code": "WBS-ELE-0", "name": "Electrical Works (L5)", "level": 5, "parent_code": None},
    {"code": "WBS-MEC-0", "name": "Mechanical Works (L5)", "level": 5, "parent_code": None},
    {"code": "WBS-INS-0", "name": "Instrumentation Works (L5)", "level": 5, "parent_code": None},
    # L6 children
    {"code": "PIP-204", "name": "Rack R-204 Piping (L6)", "level": 6, "parent_code": "WBS-PIP-0"},
    {"code": "PIP-210", "name": "Rack R-210 + Yard Piping (L6)", "level": 6, "parent_code": "WBS-PIP-0"},
    {"code": "CIV-204", "name": "B-Block + Pump-House Civil (L6)", "level": 6, "parent_code": "WBS-CIV-0"},
    {"code": "ELE-200", "name": "Electrical Systems (L6)", "level": 6, "parent_code": "WBS-ELE-0"},
    {"code": "MEC-200", "name": "Mechanical Erection (L6)", "level": 6, "parent_code": "WBS-MEC-0"},
    {"code": "INS-200", "name": "Instrumentation Systems (L6)", "level": 6, "parent_code": "WBS-INS-0"},
    {"code": "YARD-00", "name": "Shared Logistics / Yard-A (L6)", "level": 6, "parent_code": "WBS-PIP-0"},
]

# (code, wbs, name, discipline, location, object, action, size, tag,
#  planned_start, planned_finish, actual_start, actual_finish, progress, status)
ACTIVITIES = [
    # ---- Piping x16 ----
    ("PIP-204-017", "PIP-204", 'Erect 24" Process Line Spool at Rack R-204', "Piping", "R-204", "spool", "erect", '24"', "SPL-204-24-01", "2026-09-08", "2026-09-12", "2026-09-08", None, 60.0, "In Progress"),
    ("PIP-204-018", "PIP-204", 'Fit-up 24" Process Line Spool at Rack R-204', "Piping", "R-204", "spool", "fit-up", '24"', "SPL-204-24-01", "2026-09-12", "2026-09-14", None, None, 0.0, "Not Started"),
    ("PIP-204-019", "PIP-204", 'Welding 24" Process Line at Rack R-204', "Piping", "R-204", "weld", "weld", '24"', "W-204-24-01", "2026-09-14", "2026-09-17", None, None, 0.0, "Not Started"),
    ("PIP-204-020", "PIP-204", 'NDT of 24" Welds at Rack R-204', "Piping", "R-204", "weld", "test", '24"', "W-204-24-01", "2026-09-17", "2026-09-18", None, None, 0.0, "Not Started"),
    ("PIP-204-021", "PIP-204", 'Painting 24" Process Line at Rack R-204', "Piping", "R-204", "line", "paint", '24"', "L-204-24", "2026-09-18", "2026-09-20", None, None, 0.0, "Not Started"),
    ("PIP-204-022", "PIP-204", 'Insulation 24" Process Line at Rack R-204', "Piping", "R-204", "line", "insulate", '24"', "L-204-24", "2026-09-20", "2026-09-22", None, None, 0.0, "Not Started"),
    ("PIP-204-023", "PIP-204", 'Erect 12" Utility Spool at Rack R-204', "Piping", "R-204", "spool", "erect", '12"', "SPL-204-12-02", "2026-09-05", "2026-09-08", "2026-09-05", "2026-09-09", 100.0, "Complete"),
    ("PIP-204-024", "PIP-204", 'Hydrotest 12" Utility Line at R-204', "Piping", "R-204", "line", "hydrotest", '12"', "L-204-12", "2026-09-09", "2026-09-11", "2026-09-10", None, 40.0, "In Progress"),
    ("PIP-210-011", "PIP-210", 'Erect 24" Process Line Spool at Rack R-210', "Piping", "R-210", "spool", "erect", '24"', "SPL-210-24-01", "2026-09-10", "2026-09-14", None, None, 0.0, "Not Started"),
    ("PIP-210-012", "PIP-210", 'Fit-up 24" Spool at Rack R-210', "Piping", "R-210", "spool", "fit-up", '24"', "SPL-210-24-01", "2026-09-14", "2026-09-16", None, None, 0.0, "Not Started"),
    ("PIP-210-013", "PIP-210", 'Welding 24" Line at Rack R-210', "Piping", "R-210", "weld", "weld", '24"', "W-210-24-01", "2026-09-16", "2026-09-19", None, None, 0.0, "Not Started"),
    ("PIP-210-014", "PIP-210", 'Erect 8" Drain Line at Rack R-210', "Piping", "R-210", "line", "erect", '8"', "L-210-08", "2026-09-06", "2026-09-09", "2026-09-06", "2026-09-09", 100.0, "Complete"),
    ("PIP-YRD-015", "YARD-00", 'Receive 24" Spools at Yard-A', "Piping", "Yard-A", "spool", "receive", '24"', "SPL-24-GEN", "2026-09-01", "2026-09-04", "2026-09-01", "2026-09-04", 100.0, "Complete"),
    ("PIP-YRD-016", "YARD-00", 'Transport Spool to R-204 from Yard-A', "Piping", "Yard-A", "spool", "transport", '24"', "SPL-204-24-01", "2026-09-05", "2026-09-07", "2026-09-05", "2026-09-07", 100.0, "Complete"),
    ("PIP-204-025", "PIP-204", 'Valve Installation 24" Line at R-204', "Piping", "R-204", "valve", "install", '24"', "V-204-24-03", "2026-09-19", "2026-09-21", None, None, 0.0, "Not Started"),
    ("PIP-210-017", "PIP-210", 'Supports Fabrication for R-210 Racks', "Piping", "R-210", "support", "fabricate", "", "SUP-210", "2026-09-06", "2026-09-12", "2026-09-06", "2026-09-12", 100.0, "Complete"),
    # ---- Civil x11 ----
    ("CIV-204-031", "CIV-204", 'Excavation for Equipment Foundation at B-Block', "Civil", "B-Block", "foundation", "excavate", "", "F-204", "2026-08-25", "2026-08-30", "2026-08-25", "2026-08-31", 100.0, "Complete"),
    ("CIV-204-032", "CIV-204", 'Rebar Work Foundation B-Block', "Civil", "B-Block", "foundation", "rebar", "", "F-204", "2026-08-31", "2026-09-05", "2026-09-01", "2026-09-06", 100.0, "Complete"),
    ("CIV-204-033", "CIV-204", 'Concreting Foundation F-204 at B-Block', "Civil", "B-Block", "foundation", "concrete", "", "F-204", "2026-09-06", "2026-09-09", "2026-09-07", None, 70.0, "In Progress"),
    ("CIV-204-034", "CIV-204", 'Curing + Formwork Removal F-204', "Civil", "B-Block", "foundation", "cure", "", "F-204", "2026-09-09", "2026-09-12", None, None, 0.0, "Not Started"),
    ("CIV-204-035", "CIV-204", 'Backfilling around F-204', "Civil", "B-Block", "foundation", "backfill", "", "F-204", "2026-09-12", "2026-09-14", None, None, 0.0, "Not Started"),
    ("CIV-204-036", "CIV-204", 'Anchor Bolt Setting F-204', "Civil", "B-Block", "anchor bolt", "install", "", "F-204", "2026-09-05", "2026-09-06", "2026-09-05", "2026-09-06", 100.0, "Complete"),
    ("CIV-YRD-037", "CIV-204", 'Piling Works Pump-House PH1', "Civil", "PH1", "foundation", "pile", "", "PH1-P", "2026-08-20", "2026-08-28", "2026-08-20", "2026-08-28", 100.0, "Complete"),
    ("CIV-YRD-038", "CIV-204", 'Pile Cap Concreting PH1', "Civil", "PH1", "pile cap", "concrete", "", "PH1-P", "2026-08-29", "2026-09-02", "2026-08-29", "2026-09-03", 100.0, "Complete"),
    ("CIV-BLK-039", "CIV-204", 'Roads + Drains B-Block Phase 1', "Civil", "B-Block", "road", "construct", "", "RD-B1", "2026-09-10", "2026-09-20", "2026-09-10", None, 30.0, "In Progress"),
    ("CIV-BLK-040", "CIV-204", 'Equipment Plinth Casting B-Block', "Civil", "B-Block", "plinth", "cast", "", "PL-B2", "2026-09-15", "2026-09-18", None, None, 0.0, "Not Started"),
    ("CIV-BLK-041", "CIV-204", 'Grouting of Pump Foundations PH1', "Civil", "PH1", "foundation", "grout", "", "PH1-F", "2026-09-18", "2026-09-20", None, None, 0.0, "Not Started"),
    # ---- Electrical x10 ----
    ("ELE-204-051", "ELE-200", 'Cable Tray Erection Rack R-204', "Electrical", "R-204", "cable tray", "erect", "", "CT-204", "2026-09-01", "2026-09-06", "2026-09-01", "2026-09-06", 100.0, "Complete"),
    ("ELE-204-052", "ELE-200", 'Power Cable Laying R-204 to Substation S1', "Electrical", "R-204", "cable", "lay", "", "CB-204-S1", "2026-09-07", "2026-09-12", "2026-09-07", None, 50.0, "In Progress"),
    ("ELE-204-053", "ELE-200", 'Cable Termination MCC-204', "Electrical", "R-204", "cable", "terminate", "", "MCC-204", "2026-09-12", "2026-09-15", None, None, 0.0, "Not Started"),
    ("ELE-SUB-054", "ELE-200", 'Transformer Erection Substation S1', "Electrical", "S1", "transformer", "erect", "", "TR-S1", "2026-08-28", "2026-09-03", "2026-08-28", "2026-09-04", 100.0, "Complete"),
    ("ELE-SUB-055", "ELE-200", 'Busbar Installation S1', "Electrical", "S1", "busbar", "install", "", "BB-S1", "2026-09-04", "2026-09-08", "2026-09-05", None, 80.0, "In Progress"),
    ("ELE-SUB-056", "ELE-200", 'Earthing Grid Extension S1', "Electrical", "S1", "earthing", "extend", "", "E-S1", "2026-09-08", "2026-09-11", None, None, 0.0, "Not Started"),
    ("ELE-BLK-057", "ELE-200", 'Lighting Installation B-Block', "Electrical", "B-Block", "lighting", "install", "", "LT-B", "2026-09-12", "2026-09-18", "2026-09-12", None, 20.0, "In Progress"),
    ("ELE-BLK-058", "ELE-200", 'Control Building Wiring CR1', "Electrical", "CR1", "building", "wire", "", "CR1-W", "2026-09-15", "2026-09-22", None, None, 0.0, "Not Started"),
    ("ELE-204-059", "ELE-200", 'Loop Checking Support Power R-204', "Electrical", "R-204", "loop", "check", "", "LP-204", "2026-09-16", "2026-09-19", None, None, 0.0, "Not Started"),
    ("ELE-SUB-060", "ELE-200", 'Pre-commissioning Tests S1', "Electrical", "S1", "substation", "test", "", "S1", "2026-09-20", "2026-09-24", None, None, 0.0, "Not Started"),
    # ---- Mechanical x9 ----
    ("MEC-204-071", "MEC-200", 'Pump P-204A Erection at Pump-House PH1', "Mechanical", "PH1", "pump", "erect", "", "P-204A", "2026-09-02", "2026-09-06", "2026-09-02", "2026-09-06", 100.0, "Complete"),
    ("MEC-204-072", "MEC-200", 'Pump P-204B Erection PH1', "Mechanical", "PH1", "pump", "erect", "", "P-204B", "2026-09-06", "2026-09-10", "2026-09-06", None, 60.0, "In Progress"),
    ("MEC-204-073", "MEC-200", 'Alignment of Pump P-204A', "Mechanical", "PH1", "pump", "align", "", "P-204A", "2026-09-07", "2026-09-09", None, None, 0.0, "Not Started"),
    ("MEC-204-074", "MEC-200", 'Grouting Pump P-204A Foundation', "Mechanical", "PH1", "foundation", "grout", "", "P-204A-F", "2026-09-09", "2026-09-11", None, None, 0.0, "Not Started"),
    ("MEC-204-075", "MEC-200", 'Piping Hook-up Pump P-204A', "Mechanical", "PH1", "piping", "hook-up", "", "P-204A-H", "2026-09-11", "2026-09-14", None, None, 0.0, "Not Started"),
    ("MEC-YRD-076", "MEC-200", 'Compressor K-201 Foundation Prep', "Mechanical", "Yard-A", "foundation", "prepare", "", "K-201-F", "2026-09-03", "2026-09-08", "2026-09-03", "2026-09-08", 100.0, "Complete"),
    ("MEC-YRD-077", "MEC-200", 'Compressor K-201 Erection', "Mechanical", "Yard-A", "compressor", "erect", "", "K-201", "2026-09-09", "2026-09-15", None, None, 0.0, "Not Started"),
    ("MEC-YRD-078", "MEC-200", 'Lube Oil Flushing K-201', "Mechanical", "Yard-A", "lube oil", "flush", "", "K-201-L", "2026-09-15", "2026-09-18", None, None, 0.0, "Not Started"),
    ("MEC-204-079", "MEC-200", 'Crane Deployment Rack R-204 Support Works', "Mechanical", "R-204", "crane", "deploy", "", "CRN-204", "2026-09-06", "2026-09-07", "2026-09-06", "2026-09-07", 100.0, "Complete"),
    # ---- Instrumentation x9 ----
    ("INS-204-081", "INS-200", 'Instrument Impulse Tubing R-204', "Instrumentation", "R-204", "tubing", "install", "", "TB-204", "2026-09-08", "2026-09-14", "2026-09-08", None, 45.0, "In Progress"),
    ("INS-204-082", "INS-200", 'Pressure Transmitter PT-2041 Installation', "Instrumentation", "R-204", "transmitter", "install", "", "PT-2041", "2026-09-12", "2026-09-14", None, None, 0.0, "Not Started"),
    ("INS-204-083", "INS-200", 'Loop Checking PT-2041 Loop', "Instrumentation", "R-204", "loop", "check", "", "PT-2041", "2026-09-15", "2026-09-17", None, None, 0.0, "Not Started"),
    ("INS-CR1-084", "INS-200", 'DCS Panel Wiring Control-Room CR1', "Instrumentation", "CR1", "panel", "wire", "", "DCS-CR1", "2026-09-10", "2026-09-18", "2026-09-10", None, 35.0, "In Progress"),
    ("INS-CR1-085", "INS-200", 'DCS Loop Testing CR1', "Instrumentation", "CR1", "loop", "test", "", "DCS-CR1", "2026-09-18", "2026-09-21", None, None, 0.0, "Not Started"),
    ("INS-204-086", "INS-200", 'Control Valve CV-2041 Installation R-204', "Instrumentation", "R-204", "valve", "install", "", "CV-2041", "2026-09-13", "2026-09-15", None, None, 0.0, "Not Started"),
    ("INS-204-087", "INS-200", 'Calibration of PT-2041', "Instrumentation", "R-204", "transmitter", "calibrate", "", "PT-2041", "2026-09-14", "2026-09-15", None, None, 0.0, "Not Started"),
    ("INS-CR1-088", "INS-200", 'SCADA Communication Check CR1', "Instrumentation", "CR1", "scada", "check", "", "SCADA-1", "2026-09-21", "2026-09-23", None, None, 0.0, "Not Started"),
    ("INS-204-089", "INS-200", 'Air Header Leak Test R-204', "Instrumentation", "R-204", "air header", "test", "", "AH-204", "2026-09-06", "2026-09-08", "2026-09-06", "2026-09-08", 100.0, "Complete"),
]

RELATIONSHIPS = [
    # R-204 piping chain (demo-critical: erection -> fit-up -> welding -> NDT)
    ("PIP-204-017", "PIP-204-018", "FS"),
    ("PIP-204-018", "PIP-204-019", "FS"),
    ("PIP-204-019", "PIP-204-020", "FS"),
    ("PIP-204-020", "PIP-204-021", "FS"),
    ("PIP-204-021", "PIP-204-022", "FS"),
    ("PIP-204-019", "PIP-204-025", "FS"),
    ("PIP-204-023", "PIP-204-024", "FS"),
    # R-210 chain + material flow from yard
    ("PIP-210-011", "PIP-210-012", "FS"),
    ("PIP-210-012", "PIP-210-013", "FS"),
    ("PIP-YRD-015", "PIP-YRD-016", "FS"),
    ("PIP-YRD-016", "PIP-204-017", "FS"),
    ("PIP-210-017", "PIP-210-011", "FS"),
    # Civil chain
    ("CIV-204-031", "CIV-204-032", "FS"),
    ("CIV-204-032", "CIV-204-036", "FS"),
    ("CIV-204-036", "CIV-204-033", "FS"),
    ("CIV-204-033", "CIV-204-034", "FS"),
    ("CIV-204-034", "CIV-204-035", "FS"),
    ("CIV-YRD-037", "CIV-YRD-038", "FS"),
    ("CIV-YRD-038", "CIV-BLK-041", "FS"),
    # Electrical
    ("ELE-SUB-054", "ELE-SUB-055", "FS"),
    ("ELE-SUB-055", "ELE-SUB-056", "FS"),
    ("ELE-204-051", "ELE-204-052", "FS"),
    ("ELE-204-052", "ELE-204-053", "FS"),
    ("ELE-204-052", "ELE-204-059", "FS"),
    # Mechanical pump-A chain + compressor chain
    ("MEC-204-071", "MEC-204-073", "FS"),
    ("MEC-204-072", "MEC-204-073", "FS"),
    ("MEC-204-073", "MEC-204-074", "FS"),
    ("MEC-204-074", "MEC-204-075", "FS"),
    ("MEC-YRD-076", "MEC-YRD-077", "FS"),
    ("MEC-YRD-077", "MEC-YRD-078", "FS"),
    # Instrumentation
    ("INS-204-082", "INS-204-087", "FS"),
    ("INS-204-087", "INS-204-083", "FS"),
    ("INS-204-086", "INS-204-083", "FS"),
    ("INS-CR1-084", "INS-CR1-085", "FS"),
]

# (report_code, raw_text, source, discipline, location, date, category, linked_activity)
REPORTS = [
    # ---- clean (5) ----
    ("DPR-2026-09-18-01", "24 inch spool erection completed at R-204 on 18 Sep 2026.", "text", "Piping", "R-204", "2026-09-18", "clean", "PIP-204-017"),
    ("DPR-2026-09-09-02", "12 inch utility spool erected at Rack R-204 on 09 Sep 2026.", "text", "Piping", "R-204", "2026-09-09", "clean", "PIP-204-023"),
    ("DPR-2026-09-06-03", "Cable tray erected at Rack R-204 on 06 Sep 2026.", "text", "Electrical", "R-204", "2026-09-06", "clean", "ELE-204-051"),
    ("DPR-2026-09-06-04", "Pump P-204A erected at pump-house PH1 on 06 Sep 2026.", "text", "Mechanical", "PH1", "2026-09-06", "clean", "MEC-204-071"),
    ("DPR-2026-09-08-05", "Air header leak test completed at R-204 on 08 Sep 2026.", "text", "Instrumentation", "R-204", "2026-09-08", "clean", "INS-204-089"),
    # ---- terminology mismatch (5) ----
    ("DPR-2026-09-18-06", "Yesterday night team completed pipe erection of 24 inch line near R204.", "text", "Piping", "R-204", "2026-09-18", "mismatch", "PIP-204-017"),
    ("DPR-2026-09-17-07", "X-ray of 24 inch joints at R-204 completed.", "text", "Piping", "R-204", "2026-09-17", "mismatch", "PIP-204-020"),
    ("DPR-2026-09-13-08", "Coating applied on 24 inch process line at Rack 204.", "text", "Piping", "R-204", "2026-09-13", "mismatch", "PIP-204-021"),
    ("DPR-2026-09-07-09", "Copper laying from R-204 to substation finished halfway.", "text", "Electrical", "R-204", "2026-09-07", "mismatch", "ELE-204-052"),
    ("DPR-2026-09-09-10", "Pump P-204A trueness check pending, base ready.", "text", "Mechanical", "PH1", "2026-09-09", "mismatch", "MEC-204-073"),
    # ---- abbreviations (4) ----
    ("DPR-2026-09-18-11", "Erec. of 24in sp. R204 done.", "text", "Piping", "R-204", "2026-09-18", "abbreviation", "PIP-204-017"),
    ("DPR-2026-09-14-12", "PT-2041 cal. done at R204.", "text", "Instrumentation", "R-204", "2026-09-14", "abbreviation", "INS-204-087"),
    ("DPR-2026-09-12-13", "CT erec. R-204 done.", "text", "Electrical", "R-204", "2026-09-12", "abbreviation", "ELE-204-051"),
    ("DPR-2026-09-10-14", "Fdn concreting F-204 70pct.", "text", "Civil", "B-Block", "2026-09-10", "abbreviation", "CIV-204-033"),
    # ---- incomplete (4) ----
    ("DPR-2026-09-15-15", "Work completed at R-204.", "text", "", "R-204", "2026-09-15", "incomplete", None),
    ("DPR-2026-09-16-16", "Welding done.", "text", "Piping", "", "2026-09-16", "incomplete", None),
    ("DPR-2026-09-11-17", "Cable work finished yesterday.", "text", "Electrical", "", "2026-09-11", "incomplete", None),
    ("DPR-2026-09-12-18", "Foundation poured.", "text", "Civil", "", "2026-09-12", "incomplete", None),
    # ---- ambiguous (3) ----
    ("DPR-2026-09-19-19", "R204 piping work completed.", "text", "Piping", "R-204", "2026-09-19", "ambiguous", None),
    ("DPR-2026-09-19-20", "All B-Block civil works done.", "text", "Civil", "B-Block", "2026-09-19", "ambiguous", None),
    ("DPR-2026-09-20-21", "Loop checking completed at site.", "text", "Instrumentation", "", "2026-09-20", "ambiguous", None),
    # ---- duplicate (4): two pairs claiming the same completion ----
    ("DPR-2026-09-09-22", "12 inch utility spool erection at R-204 completed on 09 Sep.", "text", "Piping", "R-204", "2026-09-09", "duplicate", "PIP-204-023"),
    ("DPR-2026-09-10-23", "12 inch spool at R-204 erected and completed (contractor B report, 10 Sep).", "text", "Piping", "R-204", "2026-09-10", "duplicate", "PIP-204-023"),
    ("DPR-2026-09-06-24", "Cable tray at R-204 fully erected, confirmed 06 Sep evening.", "text", "Electrical", "R-204", "2026-09-06", "duplicate", "ELE-204-051"),
    ("DPR-2026-09-07-25", "Cable tray erection R-204 done (second crew DPR 07 Sep).", "text", "Electrical", "R-204", "2026-09-07", "duplicate", "ELE-204-051"),
    # ---- contradiction (4) ----
    ("DPR-2026-09-18-26", "24 inch welding at R-204 completed on 18 Sep 2026.", "text", "Piping", "R-204", "2026-09-18", "contradiction", "PIP-204-019"),
    ("DPR-2026-09-19-27", "24 inch welding at R-204 started on 19 Sep 2026.", "text", "Piping", "R-204", "2026-09-19", "contradiction", "PIP-204-019"),
    ("DPR-2026-09-20-28", "24 inch welding at R-210 completed on 20 Sep 2026.", "text", "Piping", "R-210", "2026-09-20", "contradiction", "PIP-210-013"),
    ("DPR-2026-09-12-29", "Fit-up at R-210 not yet started as of 12 Sep (supervisor note).", "text", "Piping", "R-210", "2026-09-12", "contradiction", "PIP-210-012"),
    # ---- partial progress (3) ----
    ("DPR-2026-09-11-30", "24 inch spool erection at R-204 60 percent complete.", "text", "Piping", "R-204", "2026-09-11", "partial", "PIP-204-017"),
    ("DPR-2026-09-10-31", "Foundation concreting F-204 about 70 percent done.", "text", "Civil", "B-Block", "2026-09-10", "partial", "CIV-204-033"),
    ("DPR-2026-09-12-32", "Impulse tubing at R-204 roughly half laid.", "text", "Instrumentation", "R-204", "2026-09-12", "partial", "INS-204-081"),
    # ---- unmatched (3) ----
    ("DPR-2026-09-21-33", "Helipad lighting completed at guest house complex.", "text", "Electrical", "Guest-House", "2026-09-21", "unmatched", None),
    ("DPR-2026-09-21-34", "Boundary wall painting phase 9 completed.", "text", "Civil", "Perimeter", "2026-09-21", "unmatched", None),
    ("DPR-2026-09-22-35", "Canteen furniture installation completed.", "text", "", "Canteen", "2026-09-22", "unmatched", None),
]

EXECUTION_HISTORY = [
    {"pattern": '24" process spool erection', "discipline": "Piping", "executions": 18, "avg_planned_days": 5.0, "avg_actual_days": 6.7, "common_issues": "Material availability; Crane availability; Fit-up rework"},
    {"pattern": '24" line welding', "discipline": "Piping", "executions": 22, "avg_planned_days": 4.0, "avg_actual_days": 5.1, "common_issues": "Welder availability; Fit-up rework; Weather"},
    {"pattern": "Equipment foundation concreting", "discipline": "Civil", "executions": 30, "avg_planned_days": 4.0, "avg_actual_days": 4.6, "common_issues": "RMC delays; Curing water; Formwork reuse"},
    {"pattern": "Power cable laying", "discipline": "Electrical", "executions": 15, "avg_planned_days": 6.0, "avg_actual_days": 7.2, "common_issues": "Tray readiness; Route clearance"},
    {"pattern": "Pump erection + alignment", "discipline": "Mechanical", "executions": 12, "avg_planned_days": 5.0, "avg_actual_days": 5.4, "common_issues": "Crane availability; Foundation readiness"},
    {"pattern": "Transmitter installation + calibration", "discipline": "Instrumentation", "executions": 25, "avg_planned_days": 3.0, "avg_actual_days": 3.3, "common_issues": "Calibration lab queue; Tubing readiness"},
    {"pattern": "Hydrotest package", "discipline": "Piping", "executions": 9, "avg_planned_days": 3.0, "avg_actual_days": 4.0, "common_issues": "Water availability; Punch closure"},
    {"pattern": "DCS panel wiring + loop testing", "discipline": "Instrumentation", "executions": 7, "avg_planned_days": 9.0, "avg_actual_days": 11.5, "common_issues": "Drawing revisions; Cable availability"},
]

CONFLICTS = [
    {"conflict_type": "duplicate", "evidence_a": "DPR-2026-09-09-22", "evidence_b": "DPR-2026-09-10-23",
     "reason": "Two reports claim PIP-204-023 (12 inch spool) was completed on different dates.",
     "suggested_action": "Planner: merge evidence into PIP-204-023, keep earliest verified date."},
    {"conflict_type": "contradiction", "evidence_a": "DPR-2026-09-18-26", "evidence_b": "DPR-2026-09-19-27",
     "reason": "Report A says PIP-204-019 welding completed 18 Sep; Report B says it started 19 Sep.",
     "suggested_action": "Planner: investigate with field supervisor; do not auto-update schedule."},
    {"conflict_type": "impossible", "evidence_a": "DPR-2026-09-20-28", "evidence_b": "PIP-210-011",
     "reason": "Welding reported complete at R-210 but predecessor erection PIP-210-011 never started.",
     "suggested_action": "Planner: reject or hold for review; verify erection status first."},
]


def run_seed(db: Session | None = None) -> dict:
    """Insert (idempotently) the full synthetic project. Returns counts."""
    close = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        from app.db import ensure_columns

        ensure_columns()
        db = SessionLocal()
        close = True
    try:
        # wipe in FK-safe order
        for m in (ProjectVocabulary, AuditEvent, ReviewDecision, ScheduleUpdate, VerificationResult, MatchCandidate, ExtractedEvent, Conflict, ExecutionHistory, FieldReport, ActivityRelationship, Activity, WbsNode, Project):
            db.query(m).delete()
        db.add(Project(**PROJECT))
        for w in WBS_NODES:
            db.add(WbsNode(project_id=1, **w))
        for a in ACTIVITIES:
            (code, wbs, name, disc, loc, obj, act, size, tag, ps, pf, as_, af, prog, st) = a
            db.add(Activity(code=code, wbs_code=wbs, name=name, discipline=disc, location=loc,
                            object=obj, action=act, size=size, tag=tag, planned_start=ps,
                            planned_finish=pf, actual_start=as_, actual_finish=af,
                            progress=prog, status=st))
        for f, t, r in RELATIONSHIPS:
            db.add(ActivityRelationship(from_code=f, to_code=t, rel_type=r))
        for rc, text, src, disc, loc, dt, cat, link in REPORTS:
            db.add(FieldReport(report_code=rc, raw_text=text, source=src, discipline=disc,
                               location=loc, report_date=dt, category=cat, linked_activity_code=link,
                               source_type="SYNTHETIC"))
        for h in EXECUTION_HISTORY:
            db.add(ExecutionHistory(**h, synthetic=1))
        for c in CONFLICTS:
            db.add(Conflict(**c))
        db.commit()
        return {
            "projects": db.query(Project).count(),
            "wbs_nodes": db.query(WbsNode).count(),
            "activities": db.query(Activity).count(),
            "relationships": db.query(ActivityRelationship).count(),
            "reports": db.query(FieldReport).count(),
            "execution_patterns": db.query(ExecutionHistory).count(),
            "conflicts": db.query(Conflict).count(),
        }
    finally:
        if close:
            db.close()


if __name__ == "__main__":
    print(run_seed())
