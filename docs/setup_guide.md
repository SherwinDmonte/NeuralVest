# NeuralVest — Windows Setup Guide

> **Status:** Phase 0 draft. This guide is **executed and verified in Phase 1**. The steps marked *(Phase 2)* or later are run in those phases.
> **Target:** Windows 10/11, 8 GB RAM, no dedicated GPU, Visual Studio Code.
> **Last updated:** 2026-11-23

All commands are for **PowerShell** (VS Code's default terminal on Windows). Open it with ``Ctrl + ` ``.

---

## 1. Prerequisites Overview

| Tool | Version target | Purpose | Cost |
|---|---|---|---|
| Python | 3.12.x (64-bit) | Backend, agents, analysis | Free |
| Node.js | 26.x LTS (24.x also fine) | Frontend tooling (Vite) | Free |
| Git | latest | Version control | Free |
| VS Code | latest | IDE | Free |
| Ollama | latest | Runs the local Qwen3 models | Free (MIT) |
| MongoDB Atlas account | Free cluster | Cloud database | Free tier (limits in architecture §11) |
| GitHub account | Free | Remote repository | Free |

About **6 GB of free disk space** is needed (models about 2 GB, Python packages about 1.5 GB, node_modules about 0.5 GB, plus caches).

---

## 2. Install the Tools

### 2.1 Check what is already installed

```powershell
python --version
py --list
node --version
npm --version
git --version
ollama --version
winget --version
```

If a command says *"not recognized"*, install that tool below.

### 2.2 Install with winget (built into Windows 11)

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Git.Git -e
winget install --id Ollama.Ollama -e
```

**Close and reopen VS Code** afterwards so the updated `PATH` is picked up.

> No winget? Download the installers from python.org, nodejs.org, git-scm.com and ollama.com. In the Python installer, tick **"Add python.exe to PATH"**.

### 2.3 Configure Git

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
git config --global core.autocrlf true
```

### 2.4 VS Code extensions

```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension bradlc.vscode-tailwindcss
```

---

## 3. Ollama and the Qwen3 Models

### 3.1 Memory-saving Ollama settings (run once, then restart Ollama)

```powershell
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_NUM_PARALLEL 1
```

Then quit Ollama from the system tray and start it again (or sign out and back in) so the settings take effect.

### 3.2 Download the models

```powershell
ollama pull qwen3:1.7b
ollama pull qwen3:0.6b
ollama list
```

### 3.3 Quick test (thinking mode off)

```powershell
ollama run qwen3:1.7b --think=false "In one sentence, what is a moving average?"
```

REST API test (this is how the backend talks to Ollama):

```powershell
$body = @{
  model    = "qwen3:1.7b"
  messages = @(@{ role = "user"; content = "Reply with the word OK." })
  stream   = $false
  think    = $false
  options  = @{ num_ctx = 2048 }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://localhost:11434/api/chat -Method Post -Body $body -ContentType "application/json"
```

**Expected:** a JSON object whose `message.content` contains `OK`.

### 3.4 Measure memory use (recorded in Phase 1)

Memory use and how much is released after unloading depend on the model, the Ollama version and Windows, so they are **measured, not assumed**. Record each value in `tasks.md`:

1. **Idle baseline:** reboot, open only VS Code, wait 2 minutes. Task Manager → *Performance → Memory* → note **In use**.
2. **Model loaded:** run the REST test from §3.3 for `qwen3:1.7b`, then note **In use** again, and the memory of the `ollama` processes under *Details*.
3. **After unload:**

   ```powershell
   ollama stop qwen3:1.7b
   ollama ps        # should list no loaded model
   ```

   Wait 30 seconds and note **In use** again.
4. Repeat steps 2–3 for `qwen3:0.6b`.

The same readings from PowerShell:

```powershell
# The model runs in llama-server.exe (Ollama's runner), not in ollama.exe
Get-Process ollama*, llama-server -ErrorAction SilentlyContinue | Select-Object Name, @{n="RAM_MB";e={[math]::Round($_.WorkingSet64/1MB)}}
$os = Get-CimInstance Win32_OperatingSystem
"In use (GB): {0:N2}" -f (($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB)
```

These numbers decide the default model under the **≤ 6.5 GB peak target** (architecture.md §10).

---

## 4. Project Setup (Phase 1)

### 4.1 Backend virtual environment

```powershell
cd C:\Users\<you>\Desktop\NEURALVEST
mkdir backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If activation fails with *"running scripts is disabled on this system"*:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

When the venv is active, the prompt starts with `(.venv)`. In VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `backend\.venv\Scripts\python.exe`.

Dependencies are installed from `requirements.txt`, which is created in Phase 1:

```powershell
pip install -r requirements.txt
```

### 4.2 Frontend

```powershell
cd C:\Users\<you>\Desktop\NEURALVEST
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-router-dom axios recharts lucide-react
npm install -D tailwindcss @tailwindcss/vite
npm run dev
```

**Expected:** Vite prints `Local: http://localhost:5173/`. Open it in a browser.

Tailwind v4 is set up through the Vite plugin and `@import "tailwindcss";` in the main CSS file. The exact steps are done and verified in Phase 1.

---

## 5. Environment Variables

Real secrets go only in `backend/.env`, which is git-ignored. `backend/.env.example` is committed with placeholders.

```dotenv
# ----- App -----
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173

# ----- MongoDB Atlas (Phase 2) -----
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DB_NAME=neuralvest_db
MONGODB_TEST_DB_NAME=neuralvest_db_test
STORAGE_WARN_PCT=60
STORAGE_BLOCK_PCT=85

# ----- Ollama (Phase 4) -----
OLLAMA_BASE_URL=http://localhost:11434
LLM_PRIMARY_MODEL=qwen3:1.7b
LLM_FALLBACK_MODEL=qwen3:0.6b
LLM_NUM_CTX=2048
LLM_TIMEOUT_SECONDS=90
MAX_NEWS_ARTICLES_LLM=8
LLM_MIN_FREE_RAM_MB=1500            # below this, the 0.6B model is used for the call

# ----- Analysis -----
AGENT_EXECUTION_MODE=sequential
RISK_FREE_RATE_PCT=<value>          # Phase 8, entered manually
RISK_FREE_RATE_DATE=<YYYY-MM-DD>    # date the rate applies to
RISK_FREE_RATE_SOURCE=<description> # e.g. "RBI 91-day T-bill yield"
MARKET_DATA_MAX_YEARS=5             # configurable retention for market_data

# ----- Auth (Phase 11) -----
JWT_SECRET=<generate-locally>
JWT_EXPIRE_MINUTES=60
```

### Risk-free rate (Phase 8, decision D4)

The Sharpe ratio needs a risk-free rate. NeuralVest does not fetch it automatically; you enter it so its value, date and source are always known (they are saved with every risk report).

1. Open the RBI website press releases (rbi.org.in → Press Releases) and search for **"Treasury Bills: Full Auction Result"**.
2. Open the most recent release and find the **91-day** bill's **cut-off yield** (an annual % yield, e.g. `5.5747`).
3. In `backend/.env` set all three lines (example values; use the ones you find):
   ```dotenv
   RISK_FREE_RATE_PCT=5.5747
   RISK_FREE_RATE_DATE=2026-10-07
   RISK_FREE_RATE_SOURCE=RBI 91-day T-bill auction cut-off yield
   ```
4. Restart the backend. Until all three are set, Sharpe ratios show "unavailable" and `risk_reports` documents are not written. Update the rate occasionally (e.g. monthly).

Generate a JWT secret locally in Phase 11:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The frontend uses `frontend/.env` with `VITE_API_BASE_URL=http://localhost:8000/api` (not secret, but still kept out of git for consistency).

---

## 6. MongoDB Atlas (Phase 2, manual)

1. Sign up at <https://www.mongodb.com/cloud/atlas/register>.
2. Create a **Free** cluster (M0). Pick a region close to India (for example AWS Mumbai `ap-south-1`) if one is offered on the free tier.
3. **Database Access** → add a database user with a strong, generated password. Under *Database User Privileges* choose **Specific Privileges** → `readWrite` on database `neuralvest_db`, and a second `readWrite` on `neuralvest_db_test`. Avoid the broad *Read and write to any database* role (least privilege; see database_design.md §5.2).
4. **Network Access** → *Add Current IP Address*. If your home IP changes, add the new one. Avoid `0.0.0.0/0`.
5. **Connect → Drivers → Python**: copy the `mongodb+srv://...` URI into `backend/.env` as `MONGODB_URI` and replace `<password>`. URL-encode special characters in the password (for example `@` → `%40`).
6. Never paste the URI into chat, code, commits or screenshots.

---

## 7. GitHub (Phase 1, manual)

1. Create an empty repository on github.com (no README, no .gitignore, because we create those locally). You choose public or private.
2. Authenticate. Git for Windows includes **Git Credential Manager**, which opens a browser login on the first push.

```powershell
cd C:\Users\<you>\Desktop\NEURALVEST
git init
git add .
git status            # check: no .env, no .venv, no node_modules
git commit -m "chore: initial project scaffold"
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

---

## 8. Running the App (from Phase 2 / Phase 6 onward)

Use two terminals:

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
```

```powershell
# Terminal 2 — frontend
cd frontend
npm run dev
# App: http://localhost:5173
```

Ollama runs in the background as a tray app on `http://localhost:11434`.

### Orchestration settings (Phase 10, optional)

The defaults in `.env.example` suit 8 GB RAM. `AGENT_EXECUTION_MODE=parallel` runs News, Stock Analysis and
Risk at the same time (only network waits overlap; AI calls stay one at a time). `WORKFLOW_CHECKPOINTS=true`
also needs `pip install langgraph-checkpoint-sqlite`. `REPORT_LLM_SUMMARY=false` skips the AI key observations
(about 10 s faster; the rule-based readings are used). The full report of an analysis:
`GET http://localhost:8000/api/analysis/<request_id>/report`.

### Portfolio analysis (Phase 9)

From `backend/` with the venv active and Ollama running:

```powershell
python scripts/run_analysis.py RELIANCE TCS INFY --amount 100000 --risk moderate --no-gdelt
```

Expected (numbers depend on the day): every agent `completed`/`partial`, then a `PORTFOLIO` block with one
line per stock (weight, whole shares, rupee amount), the leftover cash, the in-sample figures and a
`backtest ... CAGR ... | equal weight ... | NIFTY 50 ...` line. In the dashboard, type several symbols
separated by commas; an amount field and a risk preference appear. Without the LLM, quick results:
`POST /api/portfolio/optimize` and `POST /api/portfolio/backtest` (see http://localhost:8000/docs).

### Accounts, reports and PDF (Phase 11)

1. Generate a JWT secret **locally** (from `backend/`, venv active) and paste it into `backend/.env` as
   `JWT_SECRET=...` (replace the `<generate-locally>` placeholder). Never share or commit it:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Restart the API. Without it, `/api/auth/*` returns 503 ("Authentication is not configured").
2. In Swagger (http://localhost:8000/docs): `POST /api/auth/register`, then `POST /api/auth/login`. Copy
   `access_token`, click **Authorize** (top right), paste it, and try `GET /api/auth/me` and `GET /api/reports`.
3. Analyses started while logged in belong to you; others cannot open them. Older reports (and analyses
   started from the dashboard, which has no login yet) have no owner. To list them under your account:

   ```powershell
   python scripts/assign_reports.py --email you@example.com          # dry run: shows the counts
   python scripts/assign_reports.py --email you@example.com --apply  # assigns them
   ```

4. PDF: the dashboard's report card has a **Download PDF** button, or open
   `http://localhost:8000/api/reports/<report_id>/pdf` (the `report_id` is in `GET /api/analysis/<request_id>`).
   The PDF is generated from the stored report each time (about 0.5 s) and is not saved on disk.

Since Phase 12, `AUTH_REQUIRED` defaults to `true`: the web app asks you to log in, and the API refuses
analyses without a token. Set `AUTH_REQUIRED=false` only to call the API anonymously while testing.

### The web app (Phase 12)

After pulling Phase 12, install the new frontend packages once (Geist fonts and Phosphor icons):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The landing page is public; **Create a free account** (or **Log in**) opens the
app at `/app`: Dashboard, Stock analysis, Agent monitoring, Financial news, Portfolio, Risk analysis and
Reports. The login lasts until the token expires (`JWT_EXPIRE_MINUTES`) or the browser tab is closed.
Rate limits (`RATE_LIMIT_*`) answer 429 with a `Retry-After` header; they reset when the API restarts.

### The redesigned app (Phase 12B)

Phase 12B adds the `motion` animation package. After pulling it, run `npm install` once more in `frontend`.
The app has dark and light themes (top bar → theme menu, or Settings; "System" follows Windows), a
collapsible sidebar, `Ctrl K` search, and new pages: Market intelligence, Watchlist, Settings and Help.
The first visit to Overview or Market intelligence downloads 30 curated stocks for the breadth figures
and can take up to a minute; later visits use the cache.

The landing page quotes one real analysis. To refresh it from your latest finished run with two or more
stocks, run `python scripts/make_landing_snapshot.py` in `backend` (venv active; it only reads the database)
and commit the updated `frontend/src/landing/snapshot.json`.

---

## 9. Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `auth_not_configured` (503) on login/register | `JWT_SECRET` missing or shorter than 32 characters | Generate one (section 8, Phase 11) and restart the API |
| `token_expired` (401) | The token is older than `JWT_EXPIRE_MINUTES` | Log in again |
| `rate_limited` (429) | Too many requests in the window | Wait the `Retry-After` seconds |
| A report you can see in MongoDB answers 404 | It belongs to another account, or has no owner while `AUTH_REQUIRED=true` | Log in as the owner, or run `scripts/assign_reports.py` |

| Symptom | Cause | Fix |
|---|---|---|
| `python` opens the Microsoft Store | App-execution alias | Settings → Apps → Advanced app settings → App execution aliases → turn off `python.exe` / `python3.exe`; use `py -3.12` |
| `Activate.ps1 cannot be loaded` | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pip install` builds from source and fails | No wheel for your Python version | Make sure the venv uses Python 3.12 64-bit (`python -c "import sys; print(sys.version)"`) |
| `ServerSelectionTimeoutError` (Mongo) | IP not allow-listed, wrong password, or network blocks port 27017 | Re-add the current IP in Atlas; check the URI encoding; try another network |
| `ollama: connection refused` | Ollama not running | Start Ollama from the Start menu |
| Ollama response very slow / PC freezes | RAM pressure | Close apps, use `qwen3:0.6b`, keep `num_ctx` at 2048, run `ollama stop <model>` after use |
| Qwen3 output contains `<think>` text | Thinking mode active | Send `"think": false` on `/api/chat`; the backend also strips `<think>` blocks |
| yfinance returns an empty DataFrame | Wrong suffix, Yahoo rate limit, or Yahoo change | Use `.NS`/`.BO`; wait and retry; upgrade yfinance |
| Frontend `CORS error` | Backend CORS origin mismatch | `CORS_ORIGINS=http://localhost:5173` in `.env` |
| `npm` not recognized | Node not on PATH | Reopen VS Code after installing; reinstall Node LTS |
