# Start BRIDGE-X frontend on :5173 (expects API at http://127.0.0.1:8000).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\frontend"
npm run dev
