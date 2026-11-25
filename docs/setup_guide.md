# NeuralVest Windows Setup Guide

How to install and run NeuralVest on a Windows 10 or 11 laptop with 8 GB of RAM and no graphics card. Every
tool is free. Commands are for **PowerShell** (the default terminal in VS Code; open it with ``Ctrl + ` ``).

**Time needed:** about an hour, most of it downloads. **Disk space:** about 6 GB (models about 2 GB, Python
packages about 1.5 GB, `node_modules` about 0.5 GB, plus caches).

---

## Contents

1. [Install the tools](#1-install-the-tools)
2. [Ollama and the Qwen3 models](#2-ollama-and-the-qwen3-models)
3. [Get the code](#3-get-the-code)
4. [Backend](#4-backend)
5. [Frontend](#5-frontend)
6. [MongoDB Atlas](#6-mongodb-atlas)
7. [Configuration](#7-configuration)
8. [Run the app](#8-run-the-app)
9. [Optional settings and scripts](#9-optional-settings-and-scripts)
10. [Tests and measurements](#10-tests-and-measurements)
11. [Common errors](#11-common-errors)

---

## 1. Install the tools

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12.x, 64-bit | Backend, agents and calculations |
| Node.js | 22 LTS or newer | Frontend (Vite) |
| Git | latest | Getting and updating the code |
| Ollama | latest | Runs the local Qwen3 models |
| VS Code | latest (optional) | Editor |
| MongoDB Atlas account | free M0 cluster | Database (section 6) |

Check what is already installed:

```powershell
py --list
node --version
git --version
ollama --version
```

Install anything missing with winget (built into Windows 11), then **close and reopen the terminal** so the new
`PATH` is used:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Git.Git -e
winget install --id Ollama.Ollama -e
```

No winget? Use the installers from python.org, nodejs.org, git-scm.com and ollama.com.

Python 3.12 is required: some packages (cvxpy among them) have no ready-made wheels for other versions on Windows.
If `python` opens the Microsoft Store, see [Common errors](#11-common-errors).

---

## 2. Ollama and the Qwen3 models

Keep one model in memory at a time (run once, then quit Ollama from the system tray and start it again):

```powershell
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_NUM_PARALLEL 1
```

Download both models:

```powershell
ollama pull qwen3:1.7b
ollama pull qwen3:0.6b
ollama list
```

Quick test, with thinking mode off as the app uses it:

```powershell
ollama run qwen3:0.6b --think=false "In one sentence, what is a moving average?"
```

The app uses the 1.7B model when enough RAM is free and the 0.6B model otherwise (`LLM_MIN_FREE_RAM_MB`,
section 7). Measured on the development laptop: 1.7B needs 1.5 to 1.7 GB and writes 15 to 16 tokens per second;
0.6B needs about 0.9 GB and writes 31 to 35 tokens per second ([testing report](testing_report.md) §4).

---

## 3. Get the code

```powershell
cd $HOME\Desktop
git clone https://github.com/SherwinDmonte/NeuralVest.git NEURALVEST
cd NEURALVEST
```

---

## 4. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation fails with *"running scripts is disabled on this system"*, allow local scripts once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

While the virtual environment is active the prompt starts with `(.venv)`. In VS Code choose it with
`Ctrl+Shift+P` → *Python: Select Interpreter* → `backend\.venv\Scripts\python.exe`.

---

## 5. Frontend

In a second terminal:

```powershell
cd $HOME\Desktop\NEURALVEST\frontend
npm install
Copy-Item .env.example .env
```

`frontend/.env` holds only the API address (`VITE_API_BASE_URL=http://localhost:8000/api`). Only variables
starting with `VITE_` reach the browser, so never put secrets there.

---

## 6. MongoDB Atlas

1. Sign up at <https://www.mongodb.com/cloud/atlas/register> and create a **Free (M0)** cluster. Choose a region
   near India (for example AWS Mumbai, `ap-south-1`) if the free tier offers one.
2. **Database Access** → add a database user with a generated password. Least privilege: *Specific Privileges* →
   `readWrite` on `neuralvest_db` and `readWrite` on `neuralvest_db_test`. (Without the `dbAdmin` role the app
   cannot update an existing collection's validator later; it reports this in `/api/health/db` and keeps working.)
3. **Network Access** → *Add Current IP Address*. Add the new address if your home IP changes; avoid
   `0.0.0.0/0`.
4. **Connect → Drivers → Python**: copy the `mongodb+srv://...` address for the next section. Replace `<password>`
   and URL-encode special characters in it (for example `@` becomes `%40`).

Never paste the address with its password into chat, code, commits or screenshots.

---

## 7. Configuration

```powershell
cd $HOME\Desktop\NEURALVEST\backend
Copy-Item .env.example .env
notepad .env
```

`backend/.env` is ignored by git; only `.env.example` (placeholders) is in the repository. Fill in these values:

| Setting | What to enter |
|---|---|
| `MONGODB_URI` | The Atlas address from section 6, with the real password |
| `JWT_SECRET` | A random secret of at least 32 characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `RISK_FREE_RATE_PCT`, `RISK_FREE_RATE_DATE`, `RISK_FREE_RATE_SOURCE` | The RBI 91-day Treasury bill yield (below). Without all three, Sharpe ratios show as unavailable |
| `STORAGE_RESERVED_MB` | Only if other projects share the Atlas cluster: the megabytes they use, from the Atlas UI |

Everything else can stay as it is. The defaults suit an 8 GB laptop.

**Risk-free rate.** On rbi.org.in → *Press Releases*, search for **"Treasury Bills: Full Auction Result"**, open the
latest release and take the **91-day** bill's cut-off yield. For example:

```dotenv
RISK_FREE_RATE_PCT=5.8602
RISK_FREE_RATE_DATE=2026-11-18
RISK_FREE_RATE_SOURCE=RBI 91-day T-bill auction cut-off yield
```

The value, date and source are saved with every risk report. Update them now and then (monthly is enough) and
restart the API.

**Memory.** `LLM_MIN_FREE_RAM_MB=3000` means the 1.7B model is used only when 3 GB is free (counting what an
already loaded 1.7B model holds); otherwise the 0.6B model answers. Set `LLM_PRIMARY_MODEL=qwen3:0.6b` to always
use the smaller model.

---

## 8. Run the app

Ollama runs in the background as a tray app. Then use two terminals:

```powershell
# Terminal 1: API
cd $HOME\Desktop\NEURALVEST\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

```powershell
# Terminal 2: web app
cd $HOME\Desktop\NEURALVEST\frontend
npm run dev
```

| Address | What |
|---|---|
| http://localhost:5173 | The web app |
| http://localhost:8000/docs | API documentation (Swagger UI) |
| http://localhost:8000/api/health/db | Database connection check (expect `"connected": true`) |
| http://localhost:8000/api/health/llm | Ollama check: installed models and which one would answer |

**First use.** Open http://localhost:5173, choose **Create a free account**, then **Stock analysis** and enter one or
more symbols (`RELIANCE`, `TCS`, or a BSE code such as `500325`). Add an amount and a risk preference for two or
more stocks to get an illustrative portfolio. One stock takes about a minute and five stocks with a portfolio about
four minutes on an 8 GB laptop. The first visit to the Overview or Market pages downloads 30 curated stocks and can
take up to a minute; later visits use the cache.

Close heavy programs (many browser tabs, games) before an analysis. The app keeps working with little memory, but
then it uses the smaller model.

---

## 9. Optional settings and scripts

| Setting in `backend/.env` | Effect |
|---|---|
| `AGENT_EXECUTION_MODE=parallel` | News, stock analysis and risk run at the same time after market research (only network waits overlap; AI calls stay one at a time) |
| `REPORT_LLM_SUMMARY=false` | Skips the AI-written key observations (about 10 s faster; the rule based readings are used) |
| `WORKFLOW_CHECKPOINTS=true` | LangGraph checkpoints; also needs `pip install langgraph-checkpoint-sqlite` |
| `AUTH_REQUIRED=false` | Lets the API run analyses without a login (for testing only) |
| `RATE_LIMIT_*` | Requests per user per window, as `<count>/<second\|minute\|hour\|day>` |

GDELT news is off by default and can be switched on per analysis in the app. It adds about 25 to 35 seconds and is
often rate limited.

Scripts, run from `backend` with the virtual environment active:

| Command | What it does |
|---|---|
| `python scripts/run_analysis.py RELIANCE TCS --amount 100000 --risk moderate --no-gdelt` | Runs a full analysis in the terminal and prints every agent's result |
| `python scripts/assign_reports.py --email you@example.com` | Lists reports without an owner (add `--apply` to give them to that account) |
| `python scripts/make_landing_snapshot.py` | Copies the figures quoted on the landing page from your latest finished multi-stock run (read only) into `frontend/src/landing/snapshot.json` |
| `python scripts/export_openapi.py` | Writes `docs/openapi.json` from the API's routes |
| `python scripts/check_integrity.py` | Checks that stored documents still match the database rules (`--test-db` for the test database) |
| `python scripts/cleanup_market_data.py` | Shows market data older than `MARKET_DATA_MAX_YEARS` (add `--apply` to delete it) |

---

## 10. Tests and measurements

```powershell
cd $HOME\Desktop\NEURALVEST\backend
python -m pytest                                  # all tests, about 3 minutes
python -m pip install pytest-cov                  # once, for the coverage report
python -m pytest --cov=app --cov-report=term-missing:skip-covered
```

The integration tests use only the test database (`MONGODB_TEST_DB_NAME`) and are skipped when MongoDB is not
configured.

**Financial validation on real data.** The tests in `test_financial_validation.py` check every metric against
independent reference calculations on a fixed set of real prices and statements. The set is not in the
repository (Yahoo Finance data is not redistributed), so create it once; until then those tests are skipped:

```powershell
python scripts/freeze_validation_dataset.py       # 2 years of prices for 4 stocks and the NIFTY 50
```

It is saved in `data/historical/validation/` with a manifest of SHA-256 hashes, so the tests notice if the files
change. `--force` replaces it and `--end YYYY-MM-DD` chooses another cut-off date.

**Performance.** With Ollama running (uses the test database only; results go to `data/exports/`):

```powershell
python scripts/measure_performance.py             # everything, about 10 to 15 minutes
python scripts/measure_performance.py llm         # only the 1.7B and 0.6B comparison
```

The frontend has a linter: `npm run lint` in `frontend`.

---

## 11. Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `python` opens the Microsoft Store | App execution alias | Settings → Apps → Advanced app settings → App execution aliases → turn off `python.exe`; use `py -3.12` |
| `Activate.ps1 cannot be loaded` | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pip install` builds from source and fails | The virtual environment is not Python 3.12, 64-bit | Recreate it with `py -3.12 -m venv .venv` |
| `/api/health/db` shows `connected: false`, or `ServerSelectionTimeoutError` | IP not allow-listed, wrong password, or port 27017 blocked | Add your current IP in Atlas, check the password encoding, try another network |
| `database_not_configured` (503) | `MONGODB_URI` missing or still contains `<password>` | Fill it in `backend/.env` and restart the API |
| `auth_not_configured` (503) on login | `JWT_SECRET` missing or shorter than 32 characters | Generate one (section 7) and restart the API |
| `token_expired` (401) | The login is older than `JWT_EXPIRE_MINUTES` | Log in again |
| `rate_limited` (429) | Too many requests in the window | Wait the `Retry-After` seconds |
| `storage_limit_reached` (507) | The Atlas free tier is nearly full | Remove old market data: `python scripts/cleanup_market_data.py` (dry run), then `--apply` |
| A report you can see in MongoDB answers 404 | It belongs to another account, or has no owner | Log in as the owner, or run `scripts/assign_reports.py` |
| "Not Found" for a feature that should exist | The running API is older than the frontend | Restart the API (`--reload` only picks up changes while it runs) |
| `ollama: connection refused`; explanations say "generated without the AI model" | Ollama is not running | Start Ollama from the Start menu; the app works without it, using templates |
| Analyses are very slow, the laptop freezes | Not enough free RAM, Windows is paging | Close programs, or set `LLM_PRIMARY_MODEL=qwen3:0.6b` |
| Qwen3 output contains `<think>` text | Thinking mode is on | The app sends `"think": false` and removes such blocks; update Ollama if it persists |
| A stock shows no data | Wrong suffix, or Yahoo Finance rate limit | Use `.NS` (NSE) or `.BO` (BSE); wait a minute and retry |
| `CORS error` in the browser | The web app's address is not allowed | `CORS_ORIGINS=http://localhost:5173` in `backend/.env` |
| `npm` is not recognised | Node.js not on `PATH` | Reopen the terminal after installing Node.js |
