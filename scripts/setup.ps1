# BRIDGE-X one-time setup (Windows 11, py launcher + Node 24).
# Creates backend venv, installs backend + frontend deps, copies .env template.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if (-not (Test-Path '.env')) { Copy-Item .env.example .env }
if (-not (Test-Path '.venv')) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location "$root\frontend"
npm install
Write-Output 'Setup done. Start backend: scripts\run-backend.ps1, frontend: scripts\run-frontend.ps1'
