# Reseed the synthetic demo database to a clean evaluator state.
# Prefers a running backend; falls back to direct seed via venv python.
$ErrorActionPreference = 'Stop'
try {
  Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/seed | ConvertTo-Json
} catch {
  $root = Split-Path -Parent $PSScriptRoot
  Set-Location "$root\backend"
  & .\.venv\Scripts\python.exe -c "from app.db import SessionLocal,engine,Base,ensure_columns; import app.models; Base.metadata.create_all(bind=engine); ensure_columns(); from seed.synthetic_project import run_seed; from seed.oil_public_data import load_oil_knowledge; db=SessionLocal(); print(run_seed(db)); print(load_oil_knowledge(db))"
}
