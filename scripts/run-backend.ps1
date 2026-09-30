# Start BRIDGE-X backend on :8000 (venv must exist; see setup.ps1).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
