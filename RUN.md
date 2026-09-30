# How to Run BRIDGE-X

> Works fully offline with no API key (fallback mode). Two terminals needed.

## Prerequisites

- Windows 11, `py` launcher (Python 3.13), Node 24 + npm
- First-time setup only:
  ```powershell
  Set-Location D:\SIH26122\backend
  Copy-Item .env.example .env
  py -m venv .venv
  .\.venv\Scripts\Activate.ps1
  py -m pip install -r requirements.txt
  Set-Location D:\SIH26122\frontend
  npm install
  ```

## Start (every time)

Terminal 1 — backend:
```powershell
Set-Location D:\SIH26122\backend
.\.venv\Scripts\Activate.ps1
py -m uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend:
```powershell
Set-Location D:\SIH26122\frontend
npm run dev
```

## Verify

- UI: http://localhost:5173
- API health: http://127.0.0.1:8000/api/health → `"status": "ok"`
- API docs: http://127.0.0.1:8000/docs
- Seed demo data (fresh reset): `POST http://127.0.0.1:8000/api/seed`
  or Dashboard → **Reset demo data**

## Stop

`Ctrl+C` in each terminal. (If you launched detached processes instead,
`Get-Process python,node` scoped to the repo paths and `Stop-Process`.)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `:8000` health unreachable | backend terminal must stay open; check `py -m uvicorn` is running |
| UI shows "API offline" | backend down, or set `VITE_API_URL` if API is on another host/port |
| Empty dashboard (0 activities) | reseed via `POST /api/seed` |
| `py` not recognized | use the `py` launcher from python.org, or `python` if on PATH |
| Port already in use | free it: `Get-NetTCPConnection -LocalPort 8000 \| ForEach-Object { Stop-Process -Id $_.OwningProcess }` (same for 5173) |

Optional: set `OPENROUTER_API_KEY` in `backend\.env` to enable the LLM
extraction/summary path (default free model in `.env.example`). Never commit `.env`.
