# Run the full verification suite: backend pytest + frontend build + smoke.
# Backend must be running on :8000 for the smoke step (start run-backend.ps1 first).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
& .\.venv\Scripts\python.exe -m pytest -q
Set-Location "$root\frontend"
npm run build
npm run smoke
