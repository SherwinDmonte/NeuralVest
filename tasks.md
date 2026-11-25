# NeuralVest — Development Task Tracker

> **NeuralVest – AI-Powered Financial Intelligence Platform**
> Multi-agent (LangGraph + local Qwen3 via Ollama) financial intelligence system for Indian equities (NSE/BSE).
> Constraints: Windows · VS Code · 8 GB RAM · CPU only · zero software budget · GitHub-only (no live hosting).
> Starting point: the project folder is empty. The whole project is built from scratch, and there is no existing codebase to inspect.

### Rule for the `docs/` folder
- If `docs/` already exists, keep all of its existing contents unchanged. New files are only added next to them.
- If `docs/` does not exist, it is created only because the approved project structure (Section 15) requires it. It is not created for any other reason.

---

## Status Legend

| Mark | Meaning |
|------|---------|
| `[x]` | Completed (implemented **and** verified) |
| `[~]` | In Progress |
| `[ ]` | Pending |
| `[!]` | Blocked: needs manual action from the developer |

**Approval rule:** Each phase ends with a **🛑 Approval Gate**. Work on the next phase starts only after explicit approval in chat.

---

## 📍 Session Resume Pointer

> Read this block first at the start of every working session.

| Field | Value |
|-------|-------|
| Current phase | **Phase 13 (testing, performance and optimization) approved and merged into `main`; Phase 14 not started** |
| Last completed task | 13.3.3 testing report (`docs/testing_report.md`); 544 backend tests passing, 94% coverage |
| Next task | Phase 14 (final documentation and GitHub finalization) only when you say "start Phase 14" |
| Open blockers | None |
| Last updated | 2026-11-25 |

---

## Phase Overview

| # | Phase | Status | Key Deliverable |
|---|-------|--------|-----------------|
| 0 | Architecture & Planning Documentation | `[x]` approved 2026-11-23 | Architecture, schema, limitations and setup docs |
| 1 | Development Environment & Git/GitHub Setup | `[x]` approved 2026-11-23 | Working toolchain, Ollama + Qwen3, repo on GitHub |
| 2 | Backend Foundation & MongoDB Atlas | `[x]` approved 2026-11-23 | FastAPI app connected to Atlas with indexed collections |
| 3 | Financial Data Collection & Validation | `[x]` approved 2026-11-23 | Reliable market, news and fundamentals data modules |
| 4 | Local LLM Integration (Ollama + Qwen3) | `[x]` approved 2026-11-23 | Shared LLM client with prompts, JSON validation, fallback |
| 5 | MVP Agents: Market Research + Financial News | `[x]` approved 2026-11-23 | Two working agents + minimal LangGraph graph |
| 6 | MVP Dashboard & First Milestone (RELIANCE.NS) | `[x]` approved 2026-11-23 | End-to-end RELIANCE.NS analysis shown in React |
| 7 | Agent 3: Stock Analysis (Fundamentals) | `[x]` approved 2026-11-23 | Fundamental analysis agent |
| 8 | Agent 4: Risk Assessment | `[x]` approved 2026-11-23 | Risk metrics agent |
| 9 | Agent 5: Portfolio Optimization & Backtesting | `[x]` approved 2026-11-23 | Optimizer + backtester agent |
| 10 | Full LangGraph Orchestration & Report Generation | `[x]` approved 2026-11-23 | Supervisor-driven 5-agent workflow + unified report |
| 11 | Authentication, Complete API & PDF Reports | `[x]` approved 2026-11-24 | Secured REST API, reports and PDF export |
| 12 | Complete Frontend | `[x]` approved 2026-11-24 |
| 12B | UI Redesign (your master brief) | `[x]` approved 2026-11-24 | Premium redesign, dark and light themes | All 9 pages, responsive, integrated |
| 13 | Testing, Performance & Optimization | `[x]` approved 2026-11-25 | Test suite, performance report, 8 GB RAM check |
| 14 | Final Documentation & GitHub Finalization | `[ ]` | README, diagrams, reports, tagged release on GitHub |

### Why the phase order differs from the original roadmap

The original roadmap places LLM integration (Phase 6) and the frontend (Phase 8) after all five agents. The **First Development Milestone** (Section 19), however, needs LLM news summaries and a basic React dashboard for RELIANCE.NS **before** Agents 3–5 exist. To satisfy both:

- LLM integration moves earlier (Phase 4), because the News Agent needs it.
- A basic dashboard is built in Phase 6 as the MVP. The full frontend stays in Phase 12.
- LangGraph is added in Phase 5 with two nodes and grows with each agent. Phase 10 adds the full supervisor: retries, validation and the report.
- Agents 3, 4 and 5 are built one per phase, as Section 19 requires ("Do not attempt to implement all five agents simultaneously").
- Live hosting and production deployment are **excluded**. Only Git/GitHub version control is kept (Phases 1 and 14).

---

## Phase 0 — Architecture & Planning Documentation

**Objective:** Produce the design documents the prompt requires before any code is written.
**Deliverable:** Markdown documents in `docs/` that you have reviewed.

### 0.1 System & Agent Architecture
- [x] 0.1.0 Check whether `docs/` exists. If it does, keep its contents unchanged. If it does not, create it, because the approved structure (Section 15) requires it.
- [x] 0.1.1 Write the complete system architecture (React ↔ FastAPI ↔ LangGraph ↔ Ollama ↔ MongoDB Atlas ↔ data sources) → `docs/architecture.md`
- [x] 0.1.2 Write the multi-agent workflow architecture: supervisor, node order, conditional edges, failure paths
- [x] 0.1.3 Define the shared workflow state (`TypedDict`) field by field
- [x] 0.1.4 Define the input/output JSON schema contract for each of the 5 agents
- [x] 0.1.5 Define the split between work done by Python and work done by the LLM (the "no LLM numbers" rule)
- [x] 0.1.6 Define the background execution model (one worker, polling status endpoint)

### 0.2 Technology Stack Justification
- [x] 0.2.1 Justify each frontend, backend, AI, data and database choice for 8 GB RAM / zero budget
- [x] 0.2.2 Choose and pin target versions (Python, Node.js, key libraries) and verify compatibility on Windows
- [x] 0.2.3 Decide on indicator implementation: pandas-ta vs. custom NumPy/pandas (check pandas-ta's maintenance and NumPy 2 compatibility)
- [x] 0.2.4 Decide on the PDF generation library (for example ReportLab) and the authentication libraries (JWT + password hashing)
- [x] 0.2.5 Check license implications (for example, PyMuPDF is AGPL; Qwen3 and Ollama licenses) and record them

### 0.3 Database Schema Design
- [x] 0.3.1 Design all 8 collections (`users`, `stocks`, `market_data`, `financial_news`, `agent_results`, `risk_reports`, `portfolios`, `analysis_reports`) → `docs/database_design.md`
- [x] 0.3.2 Define indexes (unique keys, compound `symbol+date`, `request_id`, `user_id`) and where TTL is justified (if anywhere)
- [x] 0.3.3 Estimate storage against the Atlas M0 storage limit and set a data-retention strategy

### 0.4 Folder Structure & Roadmap
- [x] 0.4.1 Finalize the folder structure (based on Section 15; document any deviations with reasons)
- [x] 0.4.2 Confirm this phase roadmap in the architecture doc

### 0.5 Environment, Hardware & Limitations
- [x] 0.5.1 Write Windows environment setup instructions → `docs/setup_guide.md`
- [x] 0.5.2 Write the hardware/memory optimization strategy (single model, `keep_alive`, small `num_ctx`, sequential execution, caching)
- [x] 0.5.3 Check the **current** terms and limits of each external service and record them:
  - [x] yfinance / Yahoo Finance (unofficial, personal-use terms, rate limiting, delayed data)
  - [x] GDELT (rate limits, coverage of Indian news)
  - [x] RSS feeds (publisher terms, redistribution)
  - [x] NSE / BSE websites (bot protection, terms of use for automated access)
  - [x] MongoDB Atlas M0 (storage, connections, throughput limits)
  - [x] Ollama + Qwen3 (license, CPU performance expectations)
- [x] 0.5.4 Write a "data limitations & disclaimers" section (not real-time, not investment advice)

### 0.6 Review Round 1 Corrections (requested by developer, 2026-11-23)
- [x] 0.6.1 Source of truth: `agent_results` is authoritative; `analysis_reports` holds references + write-once headline summaries; `risk_reports`/`portfolios` are write-once projections (database_design §2)
- [x] 0.6.2 `agent_results` unique key uses a never-null `scope_key` instead of the nullable `symbol` (database_design §3.5)
- [x] 0.6.3 Job recovery: `queued` jobs re-queued from stored `request_params`; `running` jobs become `interrupted` with completed results kept; re-run links via `retry_of`; append-only `status_history` (database_design §6, architecture §7)
- [x] 0.6.4 Database-level safeguards: `$jsonSchema` validators (strict/error), unique indexes, least-privilege Atlas user, read-only integrity check (database_design §5)
- [x] 0.6.5 Storage estimate restated: what is included (documents + all indexes + 25% overhead), growth per analysis, scenarios, configurable retention and storage guards (database_design §4)
- [x] 0.6.6 Memory: removed the "frees about 2 GB" claim; set a ≤ 6.5 GB peak target with ≥ 1.5 GB headroom; Standard/Low-memory profiles; rule for choosing the default model from Phase 1 measurements (architecture §10, setup_guide §3.4)
- [x] 0.6.7 D1–D4 applied: pypdf replaces PyMuPDF; Python 3.12; custom indicators; risk-free rate value/date/source recorded in every risk and portfolio result
- [x] 0.6.8 Later-phase tasks updated to reflect these corrections (1.1.6, 1.4.5, 2.1.2, 2.3.6–2.3.8, 3.5.4, 4.1.7, 6.1.7–6.1.8, 8.1.5, 14.2.1)

### 🛑 Phase 0 Approval Gate
- [x] Phase 0 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 1 — Development Environment & Git/GitHub Setup

**Objective:** Get a working local toolchain and a version-controlled repository.
**Deliverable:** Verified environment, Ollama serving Qwen3, initial commit pushed to GitHub.

### 1.1 Tool Installation (Windows)
- [x] 1.1.1 Install or verify Python: **3.12.10** installed per-user from python.org (signature verified). Not added to PATH on purpose; used via `py -3.12` and the project venv. Existing 3.11.9 / 3.13.0 untouched.
- [x] 1.1.2 Install or verify Node.js LTS + npm: **Node 22.19.0 / npm 10.9.3** kept (your decision; Maintenance LTS to April 2027; meets Vite 8's `>=22.12`)
- [x] 1.1.3 Install or verify Git and configure `user.name` / `user.email`: Git 2.42 with name/email already set; `init.defaultBranch=main`; line endings via repo `.gitattributes` (no global change)
- [x] 1.1.4 Install the recommended VS Code extensions (Python, Pylance, ESLint, Tailwind CSS IntelliSense): Python/Pylance present; ESLint + Tailwind installed. Note: the Vite 8 template lints with **oxlint**, not ESLint.
- [x] 1.1.5 Install Ollama for Windows: 0.40.16 already installed; `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1` set (user env) and Ollama restarted
- [x] 1.1.6 Pull `qwen3:1.7b` and `qwen3:0.6b`; measure idle RAM, RAM with each model loaded, RAM after unload, and tokens/sec (procedure: setup_guide §3.4)

### 1.2 Project Scaffolding
- [x] 1.2.1 Create the root folder structure (`backend/`, `frontend/`, `data/`). `docs/` follows the `docs/` folder rule at the top of this file.
- [x] 1.2.2 Create the Python virtual environment in `backend/.venv` (Python 3.12.10, pip 26.3)
- [x] 1.2.3 Create `backend/requirements.txt` with pinned initial dependencies and install them: 24 top-level packages, binary wheels only, all import OK, `pip check` clean
- [x] 1.2.4 Scaffold the React app with Vite (JavaScript) in `frontend/` (Vite 8.3, React 19.3)
- [x] 1.2.5 Install and configure Tailwind CSS, React Router, Axios, Recharts and Lucide React (Tailwind 4.3 via `@tailwindcss/vite`; versions locked in `package-lock.json`)
- [x] 1.2.6 Create `backend/.env.example` (placeholders only) and `frontend/.env.example`

### 1.3 Git & GitHub
- [x] 1.3.1 `git init` and create `.gitignore` (`.env`, `.venv`, `node_modules`, `data/cache`, `__pycache__`, build outputs)
- [x] 1.3.2 Create the initial `README.md` skeleton
- [x] 1.3.3 Create the GitHub repository (public or private: your choice): https://github.com/SherwinDmonte/NeuralVest
- [x] 1.3.4 Add the remote, make the initial commit and push: `origin` = GitHub; `main` pushed (verified local = remote `a3a70b2`)
- [x] 1.3.5 Agree on a branching and commit convention: **approved** `main` + one `phase-N-<topic>` branch per phase, merged after approval; Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`)

### 1.4 Verification
- [x] 1.4.1 `python --version`, `node --version`, `git --version`, `ollama list` all succeed
- [x] 1.4.2 Ollama responds to a test prompt through its local REST API (`qwen3:0.6b`, `think: false` respected, no `<think>` output; 783 MB loaded at `num_ctx` 2048, 100% CPU; unload verified)
- [x] 1.4.3 Vite dev server starts and renders a Tailwind-styled test page (HTTP 200 on :5173; `npm run build` and `npm run lint` clean; Tailwind classes present in the CSS bundle)
- [x] 1.4.4 Confirm that no secrets are tracked by git (29 files staged; no `.env`, `.venv`, `node_modules`, `dist`)
- [x] 1.4.5 Choose the default LLM (1.7B or 0.6B) from the measurements, using the ≤ 6.5 GB peak rule (architecture §10.2); record the numbers and the decision here
  - Measured 2026-11-23 (i5-1235U, 7.68 GB usable RAM, `num_ctx` 2048, thinking off, VS Code + a few background apps open):

    | Model | Ollama-reported size | Runner process (`llama-server.exe`) | Load time | Speed |
    |---|---|---|---|---|
    | `qwen3:0.6b` | 747 MB | ~0.8–1.0 GB | 1.1–1.7 s | ~63 tokens/s |
    | `qwen3:1.7b` | 1,573 MB | ~1.4 GB | 3.4–3.6 s | ~25 tokens/s |

  - RAM in use **before** loading any model: 5.8–6.9 GB (varies with background apps). With a model loaded: 7.1–7.55 GB (93–98% of RAM). Unloading released 0.8–1.6 GB (≈ the model size).
  - **Decision (approved rule):** the measured baseline already exceeds 6.5 GB, so **`qwen3:0.6b` is the default** (`LLM_PRIMARY_MODEL`). 1.7B stays available as an opt-in when more RAM is free. Even with 0.6B, the 6.5 GB target is met only if background apps (Chrome, ChatGPT, WhatsApp, extra VS Code windows) are closed during analysis runs.
  - Good news: both models are **faster than estimated** (architecture §11 assumed 5–20 tokens/s).

### 🛑 Phase 1 Approval Gate
- [x] Phase 1 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 2 — Backend Foundation & MongoDB Atlas

**Objective:** Get a FastAPI service running with configuration, logging, error handling and a working Atlas connection.
**Deliverable:** Backend connected to MongoDB Atlas, collections and indexes created, basic stock endpoints.

### 2.1 MongoDB Atlas Setup `[!] manual`
- [x] 2.1.1 Create a MongoDB Atlas account and an M0 free cluster: **existing free cluster `cluster0` reused** (shared with the `inboxflow` project)
- [x] 2.1.2 Create a database user with a strong password and least-privilege `readWrite` on `neuralvest_db` + `neuralvest_db_test` only: **currently the existing `inboxflow` user is used.** It has admin-level rights (`collMod` succeeded). **Accepted deviation (your decision, 2026-11-23):** keep the existing Atlas user; no `neuralvest_app` user at this stage. Credentials stay only in the git-ignored `backend/.env`
- [x] 2.1.3 Configure Network Access (your current IP): connection verified
- [x] 2.1.4 Copy the connection URI into `backend/.env` (never commit it): done (password added by you); `.env` git-ignored

### 2.2 FastAPI Core
- [x] 2.2.1 `app/config.py`: settings from environment variables (Pydantic settings / python-dotenv)
- [x] 2.2.2 `app/main.py`: app factory, CORS (localhost frontend only), router registration, health endpoint
- [x] 2.2.3 Centralized exception handlers + a consistent error response schema
- [x] 2.2.4 Request ID middleware + structured logging that never logs secrets
- [x] 2.2.5 `utils/`: timing helpers and common response helpers (error envelope + `Page` schema in `schemas/common.py`)

### 2.3 Database Layer
- [x] 2.3.1 `database/database.py`: reusable PyMongo client (singleton), timeouts, connection-failure handling
- [x] 2.3.2 `database/models.py`: Pydantic document models for all 8 collections
- [x] 2.3.3 Index-creation routine run at startup (idempotent): 20 secondary indexes + 8 `_id` indexes = 28 (matches the Atlas UI)
- [x] 2.3.4 Generic repository helpers: insert with validation, upsert (no duplicates), bulk upsert in batches, paginated find (max 100)
- [x] 2.3.5 `/api/health/db` endpoint to check connectivity and report storage use (`dataSize + indexSize` vs. `STORAGE_WARN_PCT` / `STORAGE_BLOCK_PCT`)
- [x] 2.3.6 Apply `$jsonSchema` validators (strict / error) at startup; verify they are permitted on the Atlas free tier and document the fallback if not: **works on the free tier**; invalid raw writes rejected (error 121) in tests; `collMod` needs `dbAdmin` (documented)
- [x] 2.3.7 Read-only integrity check (`check_integrity`): schema violations, cross-field rules, projection mismatches, orphans. Projection check currently detects **missing sources**; value-by-value comparison is added in Phase 10, when projections are first written. Script: `scripts/check_integrity.py`
- [x] 2.3.8 Configurable market-data retention clean-up (`MARKET_DATA_MAX_YEARS`): `scripts/cleanup_market_data.py`, dry run by default

### 2.4 Basic Stock Endpoints
- [x] 2.4.1 `GET /api/stocks/{symbol}`: basic company info (stub until Phase 3, clearly marked as a placeholder): returns stored data or an honest 404; never dummy data
- [x] 2.4.2 Swagger docs reachable at `/docs` (verified with uvicorn)

### 2.5 Tests & Verification
- [x] 2.5.1 Set up pytest + test configuration (separate test database name)
- [x] 2.5.2 Unit tests for config loading and database utilities: **64 tests pass** (unit + Atlas integration on `neuralvest_db_test`; test data cleaned up afterwards)
- [x] 2.5.3 Manual check: collections and indexes are visible in the Atlas UI: confirmed by you (8 collections, 28 indexes)

### 🛑 Phase 2 Approval Gate
- [x] Phase 2 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 3 — Financial Data Collection & Validation

**Objective:** Build reliable, cached and validated data modules, with provenance recorded for every dataset.
**Deliverable:** `data/` modules with tests.

### 3.1 Symbol Handling
- [x] 3.1.1 Normalize symbols (NSE `.NS`, BSE `.BO`, plain input → default exchange) (`app/data/symbols.py`: RELIANCE, NSE:TCS, BSE:500325, 500325, ^NSEI)
- [x] 3.1.2 Detect invalid symbols (empty data / unknown ticker) (format errors raise `InvalidSymbolError`; unknown tickers raise `NoDataError` when Yahoo returns nothing)
- [x] 3.1.3 Seed a small curated list of NSE stocks for search (for example NIFTY 50 constituents) with source and date: **30 curated large-cap NSE symbols** (`seed_symbols.json`, curated 2026-11-23, explicitly *not* the official NIFTY 50 list); all 30 verified on Yahoo and stored in `stocks` via `scripts/seed_stocks.py`

### 3.2 Market Data (`data/stock_data.py`)
- [x] 3.2.1 Fetch OHLCV + adjusted close with yfinance (configurable period, default 1y) (`auto_adjust=False` keeps both close and adjusted close; retries on rate limits)
- [x] 3.2.2 Fetch the benchmark (NIFTY 50 `^NSEI`)
- [x] 3.2.3 Local file cache in `data/cache/` with a freshness window (to limit calls to Yahoo) (prices 12 h, news 60 min, profiles/financials 7 days; atomic writes)
- [x] 3.2.4 Upsert to the `market_data` collection (unique `symbol + date`) (bulk upsert; re-runs are idempotent)
- [x] 3.2.5 Record source + `fetched_at` timestamps

### 3.3 Data Validation (`data/data_validator.py`)
- [x] 3.3.1 Handle missing values (forward-fill rules, drop rules, reporting): prices are **never filled**; rows with missing prices removed and listed; missing volume → 0 and counted
- [x] 3.3.2 Detect and remove duplicate rows (stable sort, keep last)
- [x] 3.3.3 Validate dates (trading days, no future dates, sorted index) (IST trading dates, future rows removed)
- [x] 3.3.4 Check for outliers (extreme daily returns flagged, not silently removed) (> 20% daily move)
- [x] 3.3.5 Check data freshness (warn if the latest bar is stale) (stale after 3 business days; **today's partial bar flagged** during market hours)
- [x] 3.3.6 Return a validation report object attached to every dataset (`ValidationReport` with plain-language warnings)

### 3.4 News Data (`data/news_data.py`)
- [x] 3.4.1 GDELT DOC API client (company-name + ticker queries, India focus): company-name query, `sourcecountry:IN sourcelang:english`, process-wide limiter (≥ 6 s) + 15 s backoff on 429. **Best effort: rate-limited on some calls**
- [x] 3.4.2 RSS client using feedparser (curated list of Indian financial feeds, verified working): 8 feeds verified 2026-11-23 (Moneycontrol excluded: frozen since 2024); curated news aliases (e.g. RIL, HUL, L&T, SBI)
- [x] 3.4.3 Normalize articles (headline, publisher, URL, published date, source) (proper publisher names; GDELT spacing artefacts fixed)
- [x] 3.4.4 Deduplicate (by URL + fuzzy headline similarity) (URL hash + headline similarity ≥ 0.9)
- [x] 3.4.5 Validate URLs (http/https only) and treat all article text as untrusted data (no embedded credentials, tracking params stripped; HTML/scripts removed; text length-capped)
- [x] 3.4.6 Cache results and respect rate limits (backoff)

### 3.5 Fundamentals Data (`data/financial_data.py`)
- [x] 3.5.1 Get the income statement, balance sheet and cash flow (yfinance as the primary free source)
- [x] 3.5.2 Record the reporting-period date and source for each statement; flag missing or stale values (latest period per statement, key line items missing listed, stale after 18 months; banks lack Operating Income/Current Assets/Current Liabilities)
- [x] 3.5.3 Assess whether NSE/BSE filings can be accessed legitimately; if automated access is blocked or not permitted, support **manually downloaded** annual-report PDFs instead: **not permitted**: NSE Terms of Use prohibit automated data collection (Phase 0); manual PDFs supported instead
- [x] 3.5.4 PDF text extraction utility (pypdf, decision D1) for `data/financial_reports/` (`app/data/pdf_text.py`: path confined to `data/financial_reports/`, size limit, scanned pages reported)

### 3.6 Tests & Verification
- [x] 3.6.1 Unit tests for the validator using fixed sample data (no network) (13 validator tests; 133 tests in total pass)
- [x] 3.6.2 Save reproducible historical fixtures to `backend/tests/fixtures/`: **synthetic** fixtures (prices from a committed deterministic generator; RSS/GDELT samples). Real Yahoo data not committed (redistribution terms)
- [x] 3.6.3 Manual run: RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, ICICIBANK.NS fetch successfully: **5/5 succeeded** (247 valid daily rows each, stored; statements to FY2026; news via RSS + GDELT when available)

### 🛑 Phase 3 Approval Gate
- [x] Phase 3 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 4 — Local LLM Integration (Ollama + Qwen3)

**Objective:** Build one shared, memory-efficient LLM service that every agent uses.
**Deliverable:** `llm/` package with tests.

### 4.1 Ollama Client (`llm/ollama_client.py`)
- [x] 4.1.1 Single shared client (one model loaded at a time) using the Ollama REST API (`app/llm/ollama_client.py`, `get_llm_client()`; `/api/chat` over httpx)
- [x] 4.1.2 Configurable model (`qwen3:1.7b` primary → `qwen3:0.6b` fallback) (default `qwen3:0.6b`; optional fallback model; empty fallback means template)
- [x] 4.1.3 Small context window (`num_ctx`), low temperature, `keep_alive` tuning (`num_ctx` 2048, temperature 0.2, `keep_alive` 5m, `num_predict` per prompt)
- [x] 4.1.4 Handle Qwen3 "thinking" mode (disable or strip it for structured output) (`think: false` + `<think>` blocks stripped defensively)
- [x] 4.1.5 Timeouts, retry once, then fall back to the smaller model, then fall back to a deterministic (non-LLM) template (per model: 1 retry with repair hint; missing model / Ollama down: not retried; then deterministic template, so a result is always returned)
- [x] 4.1.6 Request serialization (lock / queue) so inference never runs concurrently (process-wide lock; test proves peak concurrency = 1)
- [x] 4.1.7 Free-RAM check before each call (`LLM_MIN_FREE_RAM_MB`); switch to the smaller model below the threshold; unload the model (`keep_alive: 0`) after each workflow (`psutil` free-RAM check selects the fallback model; `unload()` sends `keep_alive: 0`)

### 4.2 Structured Output
- [x] 4.2.1 JSON-mode / format-schema requests (Ollama `format` = Pydantic JSON schema)
- [x] 4.2.2 Pydantic validation of LLM output; repair or retry on invalid JSON (schema validation, JSON-in-prose recovery, truncation detected, repair retry)
- [x] 4.2.3 Guard: check that any numbers in LLM text match the computed inputs (numbers are injected, never generated) (`app/llm/guards.py`: numbers in free text must appear in the prompt, up to rounding; otherwise rejected)

### 4.3 Prompt Templates (`llm/prompts.py`)
- [x] 4.3.1 News summarization + sentiment prompt (one article per call; summary, sentiment, category, relevance)
- [x] 4.3.2 Market research explanation prompt (facts JSON from Python; template fallback built from the same facts)
- [x] 4.3.3 Prompt-injection defense: retrieved text wrapped as data, with explicit instructions to ignore any instructions inside it (`<article>` wrapper, angle brackets and control characters removed, explicit rule in the system prompt; tested)
- [x] 4.3.4 (Placeholders for prompts used by later agents; marked as such) (Phases 7–10 prompts raise `NotImplementedError`, clearly marked)

### 4.4 Tests & Verification
- [x] 4.4.1 Unit tests with a mocked LLM (valid JSON, invalid JSON, timeout, Ollama down) (31 new tests with a mock Ollama server; **164 tests pass** in total)
- [x] 4.4.2 Live test: summarize 3 real headlines; record latency and RAM use: 3 real RSS headlines. 0.6B: 1.7–4.9 s, ~45 tok/s, ~0.7 GB; 1.7B: 3.7–9.7 s, ~20 tok/s, ~1.6 GB; 1.7B classified noticeably better (`scripts/llm_smoke_test.py`)

### 🛑 Phase 4 Approval Gate
- [x] Phase 4 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 5 — MVP Agents: Market Research + Financial News

**Objective:** Build the first two specialized agents and wire them into a minimal LangGraph graph.
**Deliverable:** Both agents work on their own and through LangGraph.

### 5.1 Technical Indicators (`analysis/technical_indicators.py`)
- [x] 5.1.1 SMA 20 / 50 / 200
- [x] 5.1.2 EMA (configurable spans, for example 12/26) (pandas `ewm(adjust=False)`; documented convention)
- [x] 5.1.3 RSI (14, Wilder smoothing)
- [x] 5.1.4 MACD (12, 26, 9) + signal + histogram
- [x] 5.1.5 Bollinger Bands (20, 2σ) (population std, ddof=0)
- [x] 5.1.6 Volume analysis (average volume, volume spikes vs. 20-day average) (20-day average, ratio, spike days > 2×)
- [x] 5.1.7 Trend classification rules (bullish / bearish / sideways), documented and deterministic: close vs SMA50 vs SMA200 alignment; SMA20/SMA50 short-history rule; `insufficient_data` below 50 days
- [x] 5.1.8 Benchmark comparison (relative return vs. NIFTY 50 over matching periods) (common dates only, adjusted close)
- [x] 5.1.9 Unit tests against independently computed reference values: SMA/EMA/RSI checked value-by-value against independent loop implementations + a hand-computed RSI example (16 tests)

### 5.2 Agent 1 — Market Research (`agents/market_research.py`)
- [x] 5.2.1 Input/output Pydantic schemas (`schemas/agents.py`)
- [x] 5.2.2 Fetch → validate → compute indicators → classify trend → benchmark compare
- [x] 5.2.3 LLM-generated plain-language interpretation of the computed metrics only (facts JSON only; number guard verified live: it rejected an invented "20")
- [x] 5.2.4 Output includes the data freshness timestamp and source information
- [x] 5.2.5 Store the result in `agent_results` (+ prices of stock and benchmark in `market_data`)
- [x] 5.2.6 Agent tests (valid symbol, invalid symbol, short history < 200 days, network failure)

### 5.3 Agent 2 — Financial News (`agents/financial_news.py`)
- [x] 5.3.1 Input/output Pydantic schemas
- [x] 5.3.2 Collect → dedupe → filter by relevance to the company (ranking: company in headline first)
- [x] 5.3.3 Categorize (results, M&A, policy, regulatory, governance, legal, etc.)
- [x] 5.3.4 Sentiment: positive / negative / neutral / uncertain (LLM, with validation) (Python caps relevance: 'high' needs the company in the headline)
- [x] 5.3.5 Short summary per article + overall news digest (digest via LLM, template fallback)
- [x] 5.3.6 Store in `financial_news` (deduplicated) and `agent_results` (`agent_results` keeps url_hash references, not copies)
- [x] 5.3.7 Disclaimer: sentiment is not a prediction of returns
- [x] 5.3.8 Agent tests (no news found, LLM down, malformed feed)

### 5.4 Minimal LangGraph Workflow
- [x] 5.4.1 `orchestration/state.py`: full shared state `TypedDict` (all fields, some unused for now)
- [x] 5.4.2 `orchestration/graph.py`: Input Validation → Market Research → Financial News → Report stub (conditional edges skip agents when input or prices fail)
- [x] 5.4.3 Track `agent_status`, `errors`, `timestamps`, `data_sources`
- [x] 5.4.4 Integration test: graph run for RELIANCE.NS: offline graph tests + **live RELIANCE.NS run: all agents completed in 25 s (10.7 s cached)**; adaptive LLM used 0.6B because only ~0.5 GB RAM was free; integrity check clean (`scripts/run_analysis.py`)

### 🛑 Phase 5 Approval Gate
- [x] Phase 5 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 6 — MVP Dashboard & First Milestone (RELIANCE.NS)

**Objective:** Complete the Section 19 milestone end to end.
**Deliverable:** You enter RELIANCE.NS in React, the analysis runs in the background, and the results are saved to Atlas and displayed.

### 6.1 Backend Endpoints (MVP subset)
- [x] 6.1.1 `POST /api/analysis/start`: starts a background workflow run and returns `request_id` (HTTP 202; symbols validated → 422; storage guard 507; queue limit 429)
- [x] 6.1.2 `GET /api/analysis/{request_id}/status`: per-agent status for polling (live per-agent progress from LangGraph `stream`; queue position; after a restart derived from `agent_results`)
- [x] 6.1.3 `GET /api/analysis/{request_id}`: result (news articles joined from `financial_news` via references)
- [x] 6.1.4 `GET /api/stocks/{symbol}/history` and `/indicators` (history from MongoDB with fetch-and-store fallback; indicator series on a 2-year lookback)
- [x] 6.1.5 `GET /api/news/{symbol}` (paginated, sentiment filter)
- [x] 6.1.6 Initial market research report saved to `analysis_reports` (references + headline summaries; full outputs in `agent_results`)
- [x] 6.1.7 Job record with `request_params` and append-only `status_history`; single-worker runner (job record persisted before queuing; `ThreadPoolExecutor(max_workers=1)`; model unloaded after each job)
- [x] 6.1.8 Startup recovery: re-queue `queued` jobs, mark `running` jobs `interrupted` (keep completed results); re-run creates a new request with `retry_of` (+ `POST /api/analysis/{id}/rerun`; tested)

### 6.2 Basic React Dashboard
- [x] 6.2.1 Base layout (dark navy theme, sidebar or top nav)
- [x] 6.2.2 Axios API service layer + environment-based base URL (readable error messages from the API envelope)
- [x] 6.2.3 Symbol input + "Run Analysis" button + polling hook (2 s polling; GDELT opt-in checkbox)
- [x] 6.2.4 Price chart with SMA 20/50 (Recharts) (+ SMA200; validated palette on the navy surface)
- [x] 6.2.5 RSI and MACD panels
- [x] 6.2.6 News list with sentiment badges, summaries and source links (original headline linked to the source, above the AI summary)
- [x] 6.2.7 Basic agent status display
- [x] 6.2.8 Loading, empty and error states (+ table view for every chart; review fixes after your screenshots)

### 6.3 Milestone Verification Checklist
- [x] 6.3.1 One year of RELIANCE.NS data fetched (495 validated rows: 2-year lookback, 1-year analysis window)
- [x] 6.3.2 SMA 20, SMA 50, RSI and MACD calculated and checked against reference values: production code identical to independent reference loops on real RELIANCE data (max difference 0 over 446–481 values; the check detects deliberate errors) via `scripts/verify_indicators.py`
- [x] 6.3.3 Relevant news collected (7 articles with GDELT; 0 without GDELT at that moment, so RSS alone is not always enough)
- [x] 6.3.4 News summarized by local Qwen (7/7 by qwen3:0.6b, no fallback templates)
- [x] 6.3.5 Initial market research report generated
- [x] 6.3.6 Analysis saved in MongoDB Atlas (checked in the Atlas UI) (`scripts/milestone_check.py`: API flow, status, MongoDB)
- [x] 6.3.7 Results displayed in the React dashboard: verified by you in the browser (screenshots), review fixes applied
- [x] 6.3.8 Peak RAM use recorded during a full run: NeuralVest ≈ 1 GB (backend 169 MB + model runner 811 MB); **system peak 7.49 / 7.68 GB** with background apps open (above the 6.5 GB target because of other apps)

### 🛑 Phase 6 Approval Gate (MVP Milestone)
- [x] Phase 6 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 7 — Agent 3: Stock Analysis (Fundamentals)

**Objective:** Assess company financial health using only real retrieved data.
**Deliverable:** Stock Analysis Agent integrated into the graph.

### 7.1 Ratio Calculations (`analysis/fundamentals.py`)
- [x] 7.1.1 Revenue growth and net profit growth (YoY, multi-year where available) (YoY + CAGR; one-year jumps > 50% flagged as possible merger/acquisition, e.g. HDFC Bank FY2024)
- [x] 7.1.2 EPS, P/E, P/B (reported diluted EPS, basic as fallback; P/E and P/B use the latest close; currency check)
- [x] 7.1.3 ROE, ROA (average of opening and closing equity/assets)
- [x] 7.1.4 Debt-to-equity, current ratio (bank: current ratio not applicable, debt-to-equity not comparable)
- [x] 7.1.5 Operating margin, net margin
- [x] 7.1.6 Edge cases: negative earnings (P/E not meaningful), zero denominators, missing fields → explicit `null` + reason (loss-making, previous-year loss, zero denominators, negative equity, missing items, single year, no price, currency mismatch: all tested)
- [x] 7.1.7 Every value tagged with its source, statement period and date (each metric: value, unit, FY period, formula, inputs, reason)
- [x] 7.1.8 Unit tests with hand-computed reference values (`tests/test_fundamentals.py`; also checked by hand on real RELIANCE and HDFCBANK statements)

### 7.2 Agent 3 (`agents/stock_analysis.py`)
- [x] 7.2.1 Input/output schemas
- [x] 7.2.2 Profitability, liquidity, debt and growth assessments (rule-based) (documented thresholds; overall solid/mixed/weak)
- [x] 7.2.3 Strengths / weaknesses lists derived from the computed metrics
- [x] 7.2.4 LLM-written plain-language fundamental assessment (numbers injected) (facts only; bank debt-to-equity left out; markup/short-text guard added after a live failure)
- [x] 7.2.5 Clear flags for "unavailable" / "outdated" data (`unavailable` list with reasons; stale statements → partial)
- [x] 7.2.6 Store in `stocks` and `agent_results`
- [x] 7.2.7 Agent tests (bank stock with different statement structure, missing statements) (bank, missing statements, no price, currency mismatch, index skipped)

### 7.3 Integration
- [x] 7.3.1 Add the node to the LangGraph graph after Market Research (order: Market Research → Financial News → Stock Analysis, as in architecture §3.2; runner + API + dashboard card)
- [x] 7.3.2 Integration test with RELIANCE.NS and HDFCBANK.NS: **live RELIANCE.NS + HDFCBANK.NS: all agents completed**; ratios match hand calculations from the raw statements (`scripts/run_analysis.py`)

### 🛑 Phase 7 Approval Gate
- [x] Phase 7 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 8 — Agent 4: Risk Assessment

**Objective:** Measure the historical risk of individual stocks and of a set of stocks.
**Deliverable:** Risk Assessment Agent integrated into the graph.

### 8.1 Risk Metrics (`analysis/risk_metrics.py`)
- [x] 8.1.1 Daily and log returns; return distribution statistics (mean, std, skew, kurtosis, percentiles) (simple + log returns of the adjusted close; excess kurtosis; best/worst day)
- [x] 8.1.2 Historical and annualized volatility (252 trading days) (sample std × √252)
- [x] 8.1.3 Beta vs. NIFTY 50 (aligned dates) (inner join of dates; ≥ 60 overlapping days; correlation and R² too)
- [x] 8.1.4 Maximum drawdown (+ drawdown duration) (peak/trough/recovery dates; duration in trading days; current drawdown)
- [x] 8.1.5 Sharpe ratio using the manually configured risk-free rate (`RISK_FREE_RATE_PCT`, `_DATE`, `_SOURCE`) `[!] manual value`; the value, date and source are recorded in every risk report and portfolio result; Sharpe is not computed if any setting is missing. Rate set by developer: 5.8602% (RBI Press Release 2026-2027/1517, 91-day T-bill cut-off YTM, 2026-11-18); live Sharpe verified (RELIANCE −0.632)
- [x] 8.1.6 Correlation matrix (multi-stock) (common dates; ≥ 60 observations)
- [x] 8.1.7 Portfolio concentration (for example the Herfindahl index) (HHI + effective number of stocks; equal weights until Phase 9; caller weights via the API)
- [x] 8.1.8 Unit tests vs. reference calculations (`tests/test_risk_metrics.py`: hand examples and independent loops; real RELIANCE volatility/beta/drawdown match a separate NumPy calculation exactly)

### 8.2 Agent 4 (`agents/risk_assessment.py`)
- [x] 8.2.1 Input/output schemas
- [x] 8.2.2 Rule-based risk classification (low / moderate / high), with documented thresholds (volatility bands + drawdown bump; beta → defensive/market-like/aggressive)
- [x] 8.2.3 Diversification assessment + risk warnings (average pairwise correlation; high-correlation, deep-drawdown and high-beta warnings)
- [x] 8.2.4 LLM explanation + "historical risk is not a forecast" disclaimer (rule-based readings first; AI restates them)
- [x] 8.2.5 Store in `risk_reports` and `agent_results` (agent_results per symbol + request-scope; `risk_reports` written by the runner **when the rate is configured**)
- [x] 8.2.6 Agent tests (single stock, multiple stocks, insufficient overlapping history) (single, multiple, insufficient overlap, no benchmark, no rate)

### 8.3 Integration
- [x] 8.3.1 Add the node to the graph (reuses market data from state, so nothing is fetched twice) (after Stock Analysis; prices from state, NIFTY 50 from cache)
- [x] 8.3.2 `POST /api/risk/analyze` endpoint (synchronous, no LLM, nothing stored; optional weights; tested)

### 🛑 Phase 8 Approval Gate
- [x] Phase 8 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 9 — Agent 5: Portfolio Optimization & Backtesting

**Objective:** Produce illustrative quantitative allocations and evaluate them on historical data.
**Deliverable:** Portfolio Optimization Agent + backtester.

### 9.1 Optimization (`analysis/optimization.py`)
- [x] 9.1.1 Expected-return estimate (for example mean historical, optionally EMA) with assumptions documented (mean of daily returns x 252 (default) or EMA (span 126); last 252 trading days; assumptions recorded in every result)
- [x] 9.1.2 Covariance estimate (sample + Ledoit-Wolf shrinkage option) (Ledoit-Wolf (default) or sample, annualised)
- [x] 9.1.3 Mean-variance (efficient risk / efficient return) (`efficient_risk` / `efficient_return` (PyPortfolioOpt + cvxpy); aggressive default target documented)
- [x] 9.1.4 Minimum volatility
- [x] 9.1.5 Maximum Sharpe (falls back to min volatility, with the reason, when no stock beat the risk-free rate or the rate is missing)
- [x] 9.1.6 Equal weight
- [x] 9.1.7 Risk-based allocation (for example inverse volatility or HRP), where feasible (inverse volatility + HRP (own implementation: PyPortfolioOpt's HRPOpt is broken with SciPy 1.18))
- [x] 9.1.8 Constraints: no shorting (default), min/max weight per stock, mapping from risk preference to method/parameters (default caps raised to 1/n with a note; explicit infeasible caps are an error)
- [x] 9.1.9 Convert weights into rupee amounts and whole-share quantities (discrete allocation) + leftover cash (greedy whole-share rounding at the last close; weights stored to add up to exactly 100)
- [x] 9.1.10 Unit tests (weights sum to 1, constraints respected, edge cases such as 2 stocks or highly correlated stocks) (`test_optimization.py`: 20 tests; live weights cross-checked with an independent SciPy SLSQP solve)

### 9.2 Backtesting
- [x] 9.2.1 Walk-forward or in-sample/out-of-sample backtest (walk-forward: 252-day estimation, about 1 year out-of-sample from the 2y state data (5y via the API))
- [x] 9.2.2 Rebalancing schedule (configurable, for example monthly or quarterly) (monthly, quarterly (default) or none)
- [x] 9.2.3 Transaction-cost assumption (configurable basis points) (10 bps default on traded value; first purchase counts)
- [x] 9.2.4 Benchmark comparison vs. NIFTY 50 and equal weight
- [x] 9.2.5 Output: equity curve, CAGR, volatility, Sharpe, max drawdown
- [x] 9.2.6 Documented look-ahead-bias safeguards (weight function only receives history ending on the decision date; tested by changing future prices)

### 9.3 Agent 5 (`agents/portfolio_optimizer.py`)
- [x] 9.3.1 Input/output schemas (symbols, capital, risk preference, method, constraints) (`PortfolioOptimizationInput` / `PortfolioOutput` in `schemas/agents.py`)
- [x] 9.3.2 Waits for validated price data + risk output in the graph (conditional edge after Risk Assessment for portfolio requests (2+ stocks + amount); stocks whose risk failed are left out)
- [x] 9.3.3 LLM explanation of the allocation + "illustrative, not investment advice" disclaimer (rule-based readings shown above the labelled AI text)
- [x] 9.3.4 Store in `portfolios` and `agent_results` (agent_results (request scope) + write-once `portfolios` projection (runner, CLI script and optimize endpoint))
- [x] 9.3.5 Endpoints: `POST /api/portfolio/optimize`, `POST /api/portfolio/backtest`, `GET /api/portfolio/{portfolio_id}` (plus the analysis start body accepts `investment_amount`, `risk_preference`, `portfolio`)
- [x] 9.3.6 Agent tests (infeasible constraints, one symbol, invalid capital) (`test_agent_portfolio.py` (12) + runner/graph tests)

### 🛑 Phase 9 Approval Gate
- [x] Phase 9 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 10 — Full LangGraph Orchestration & Report Generation

**Objective:** Connect all five agents under a supervisor that validates, retries and combines their results.
**Deliverable:** Complete multi-agent workflow and unified financial intelligence report.

### 10.1 Supervisor (`orchestration/supervisor.py`)
- [x] 10.1.1 Input validation node (symbols, amount, risk preference) (symbols, amount (0 < amount <= Rs 100 crore), risk preference and portfolio options validated once; result is an `execution_plan` with the reason for every skipped agent)
- [x] 10.1.2 Routing: decide which agents run (single-stock vs. portfolio request) (`supervisor.route_*`: no symbol -> report; no prices -> report; portfolio only with amount + >= 2 validated stocks)
- [x] 10.1.3 Conditional edges for failures (skip dependent agents, mark partial results) (dependent agents skip symbols without prices; failed sections are marked unavailable with the reason)
- [x] 10.1.4 Retry policy for recoverable errors (network, LLM timeout) with limits (three layers: data fetch retries (Phase 3), LLM repair/fallback/template (Phase 4), and new: one supervisor retry for temporary source failures (`retryable`), 5 s delay, 15-min budget; plus LangGraph RetryPolicy for transient exceptions)
- [x] 10.1.5 Output validation node before Portfolio Optimization (includes the deferred Phase 9 review item: reject AI text that contradicts a rule-based reading, e.g. "the benchmark underperformed" when the stock did; remove loose benchmark fields from the market facts) (impossible values repaired and recorded; contradiction guard in the LLM client (retry -> fallback -> template) and a second check here; loose benchmark fields removed from the market facts)
- [x] 10.1.6 Sequential execution by default; optional parallel fan-out for News / Stock Analysis / Risk behind a config flag (`AGENT_EXECUTION_MODE=parallel`: fan-out + deferred join; tested to give identical results)

### 10.2 State & Checkpointing
- [x] 10.2.1 Finalize the shared state, with reducers for concurrent updates (supervisor fields + `retries` reducer; price records are plain floats (numpy values found by the checkpoint test))
- [x] 10.2.2 Optional lightweight checkpointing (SQLite, used only for LangGraph checkpoints, never as the app database) (`WORKFLOW_CHECKPOINTS=true` + `pip install langgraph-checkpoint-sqlite` (off by default); wiring tested with LangGraph's in-memory saver)
- [x] 10.2.3 Per-agent execution time + status persisted for monitoring (`analysis_reports.agent_runs` (start, end, duration, status, retries per node) + `validation_summary`)

### 10.3 Report Generation
- [x] 10.3.1 Report sections: company overview, market summary, technical analysis, news summary, sentiment, fundamentals, financial health, risk, portfolio (if requested), key observations, data limitations, source references, timestamp (`services/report_generator.py`; `GET /api/analysis/{id}/report`)
- [x] 10.3.2 Metric explanations (glossary-style, for non-technical readers) (22 plain-language entries; only the terms the report shows)
- [x] 10.3.3 Check that every number in the report traces back to an agent output (every numeric value and every number in the AI observations checked against agent outputs; untraced AI text -> template)
- [x] 10.3.4 Save to `analysis_reports` (`final_summary` (also written by the CLI script))

### 10.4 Tests
- [x] 10.4.1 Integration tests: full run, single-agent failure, LLM unavailable, invalid symbol (`test_workflow.py` + `test_supervisor.py` (30 tests); 360 tests in total)
- [x] 10.4.2 Check RAM use during a full 5-agent run (live RELIANCE + TCS + Rs 1,00,000: 80-94 s, lowest free RAM 0.28-0.47 GB with other apps open (0.54 GB free before the run); the adaptive 0.6B model was used)

### 🛑 Phase 10 Approval Gate
- [x] Phase 10 completion summary posted in chat
- [x] Developer approval received (2026-11-23)

---

## Phase 11 — Authentication, Complete API & PDF Reports

**Objective:** Secure the API and complete every endpoint.
**Deliverable:** Full REST API documented in Swagger.

### 11.1 Authentication
- [x] 11.1.1 `POST /api/auth/register`: validation + password hashing (Argon2id via pwdlib; 8-128 characters, common passwords and the e-mail itself rejected; duplicate e-mail 409)
- [x] 11.1.2 `POST /api/auth/login`: JWT access token (HS256, `JWT_EXPIRE_MINUTES`, default 60); one generic error for wrong e-mail or password
- [x] 11.1.3 `GET /api/auth/me`
- [x] 11.1.4 Auth dependency (`api/deps.py`) protecting user-specific routes; reports and portfolios scoped by `user_id` (other users' ids answer 404). `AUTH_REQUIRED=false` by default until the login pages exist (Phase 12); `scripts/assign_reports.py` gives older unowned reports to an account
- [x] 11.1.5 JWT secret in `.env` (generated locally) `[!] manual` (done: login works, 2026-11-24)

### 11.2 Remaining Endpoints
- [x] 11.2.1 `GET /api/stocks/search` (stored companies + curated list; works without MongoDB)
- [x] 11.2.2 `GET /api/news/{symbol}/sentiment` (stored articles, same rule as the News Agent)
- [x] 11.2.3 `GET /api/analysis/{request_id}/report` (Phase 10; now user-scoped, returns `report_id` and `pdf_url`)
- [x] 11.2.4 `GET /api/reports` (paginated, filters `status` and `symbol`), `GET /api/reports/{report_id}`
- [x] 11.2.5 `GET /api/reports/{report_id}/pdf`

### 11.3 Reliability & Security
- [x] 11.3.1 Rate limiting on expensive endpoints (auth per IP; analysis start/re-run, portfolio and PDF per user or IP); 429 with `Retry-After`
- [x] 11.3.2 Request timeouts on external calls (audit: Ollama, RSS, GDELT already bounded; yfinance price download now uses `HTTP_TIMEOUT_SECONDS`; other yfinance calls use the library's 30 s)
- [x] 11.3.3 Validate external URLs before storing (Phase 3) and again before returning them or writing them into a PDF (`utils/urls.py`)
- [x] 11.3.4 Review: no secrets in logs (bearer tokens/JWTs now masked too), responses or the repository

### 11.4 PDF Export
- [x] 11.4.1 PDF report template (sections from 10.3.1, tables, disclaimer on page 1 and in every footer)
- [x] 11.4.2 Embed charts in the PDF (ReportLab graphics: price, allocation, backtest equity curve)

### 11.5 Tests
- [x] 11.5.1 API tests with FastAPI TestClient (auth flow, protected routes, pagination, error codes) + unit tests (tokens, hashing, URLs, rate limiter, PDF)

### 🛑 Phase 11 Approval Gate
- [x] Phase 11 completion summary posted in chat
- [x] Developer approval received (2026-11-24)

---

## Phase 12 — Complete Frontend

**Objective:** Build a professional, responsive fintech UI covering all features.
**Deliverable:** All pages integrated with the backend.

### 12.1 Design System
- [x] 12.1.1 Theme tokens in `index.css`: graphite surfaces from the approved dark list, one accent `#3987e5`, Geist + Geist Mono, named text styles (Heading, Title, Body, Button, Caption, Figure), one easing curve. **Changed from "navy background, blue/cyan accents" at your decision (2026-11-24)**
- [x] 12.1.2 Reusable components (`components/ui.jsx`): Button, Field, Input, Select, Checkbox, Card, PageHeader, StatTile, Traced, ToneBadge, Tabs, table styles, Skeleton, ErrorState, EmptyState, Disclaimer; plus SymbolPicker, WatchButton, Logo
- [x] 12.1.3 Charts (`components/charts.jsx`): line (price, RSI, equity, mini), composed (MACD), share bars (allocation), stacked sentiment bar, correlation heatmap; each with a table view; palette validated on `#1F1F1F`
- [x] 12.1.4 App layout (`layouts/AppShell.jsx`): 248px sidebar, full height mobile menu, skip link

### 12.2 Authentication UI
- [x] 12.2.1 Register and login pages with client side validation
- [x] 12.2.2 Token in sessionStorage (cleared when the tab closes; no cookies) + Axios interceptor + logout; a 401 returns to the login page
- [x] 12.2.3 Protected routes (`/app/*`); `AUTH_REQUIRED` now defaults to `true`

### 12.3 Pages
- [x] 12.3.1 Landing page (landing-page-design + unslop skills): hero with a coded product preview, problem, benefits, tagline reveal, how it works, agents and tech stack, evidence, FAQ, final CTA, footer; privacy, terms, branded 404, meta and og image
- [x] 12.3.2 Dashboard: NIFTY 50 overview, search, recently analysed, watchlist, latest news, agent status, recent reports
- [x] 12.3.3 Stock Analysis page: overview, price chart, performance, indicators, fundamentals, news, risk, portfolio and report
- [x] 12.3.4 AI Agent Monitoring page: 6 step cards (status, progress, time, output, errors, retries) + LangGraph workflow diagram + status history + output validation
- [x] 12.3.5 Financial News page: list, sentiment filters, pagination, sentiment breakdown, source links
- [x] 12.3.6 Portfolio Optimization page: stock picker, amount, risk preference, method, constraints, rebalancing, cost; allocation, amounts, metrics, backtest chart
- [x] 12.3.7 Risk Analysis page: volatility, beta, drawdown, Sharpe, correlation heatmap, classification, concentration and diversification
- [x] 12.3.8 Reports page: list (paginated, status filter), view with raw agent outputs, compare two, download PDF

### 12.4 Quality
- [x] 12.4.1 Responsiveness checked in Edge at 1440px and 390px: no horizontal overflow on any page
- [x] 12.4.2 Skeleton loading, empty and error states on every page
- [x] 12.4.3 Accessibility basics: focus rings, labels, skip links, aria on tabs, menus and combobox, colour never alone, reduced motion
- [x] 12.4.4 Watchlist persisted per user: `watchlist` field on `users` (your decision 2026-11-24), `GET/PUT /api/auth/me/watchlist`, at most 20 symbols

### 🛑 Phase 12 Approval Gate
- [x] Phase 12 completion summary posted in chat
- [x] Developer approval received (2026-11-24, together with the Phase 12B redesign decisions)

---

## Phase 12B — UI Redesign (from your master redesign brief, 2026-11-24)

**Objective:** Turn the working Phase 12 frontend into a premium fintech interface with a distinct brand, dark and light themes and richer interaction, without losing any working feature or showing invented data.
**Deliverable:** Redesigned app and landing page in both themes, checked at 1920/1440/1366/1024/768/390/360px.

**Decisions (2026-11-24):** your brief wins fully on visual style (navy palette, brand gradients, glassmorphism, ambient lighting, gradient logo and buttons), overriding the unslop and landing-page-design rules that conflict; market breadth (gainers, losers, advancers, decliners) computed across the 30 curated stocks and labelled as such; `motion` (Framer Motion) for animation, loaded only in the signed-in app. Assumptions: Phosphor icons and Geist kept; the brief's welcome heading replaces unslop's no-greeting rule.

### 12B.1 Design system and brand
- [x] 12B.1.1 Navy dark tokens + full light theme (own shadows, borders, gradients, chart colours validated with the dataviz script)
- [x] 12B.1.2 Theme switcher: OS preference on first visit, saved in localStorage, applied before first paint, every page/chart/tooltip/table
- [x] 12B.1.3 Logo: SVG neural "N" with nodes and a rising line; gradient, transparent, light and dark versions; subtle node/line animation
- [x] 12B.1.4 Shared components restyled (buttons, cards, glass panels, dropdowns, modal, toasts, skeletons, status indicators)

### 12B.2 App shell
- [x] 12B.2.1 Collapsible sidebar (tooltips when collapsed), mobile drawer, 9 navigation items, settings, help, profile (system and model status moved to Settings only, your request 2026-11-24)
- [x] 12B.2.2 Top bar: page title, global stock search, notifications (your own events only), theme switcher, profile menu (data freshness badge removed at your request; dates stay on each card and chart). App footer: one row with the notice and privacy and terms links
- [x] 12B.2.3 Page transitions with reduced motion support

### 12B.3 Backend additions (no change to existing behaviour)
- [x] 12B.3.1 `GET /api/health/llm` (Ollama reachable, installed models) for the model status indicator
- [x] 12B.3.2 `GET /api/stocks/{symbol}/financials` (annual income statement, balance sheet, cash flow; already fetched and cached)
- [x] 12B.3.3 Market breadth across the 30 curated stocks (gainers, losers, advancers, decliners), cached, clearly labelled
- [x] 12B.3.4 Confirm SENSEX (`^BSESN`) works with the existing indicators endpoint
- [x] 12B.3.5 Tests for every new endpoint

### 12B.4 Pages
- [x] 12B.4.1 Overview: hero, NIFTY 50 and SENSEX cards with sparklines, large area chart with date ranges, breadth, recently analysed, news, watchlist, agent activity
- [x] 12B.4.2 Market Intelligence (new): index charts and market news
- [x] 12B.4.3 Stock Analysis with tabs (overview, chart with volume, fundamentals, statements, news, AI analysis)
- [x] 12B.4.4 AI Agents: animated supervisor and five agent network driven only by API status
- [x] 12B.4.5 Financial News, Risk (distribution, historical VaR), Portfolio (donut, allocation bars, risk-return scatter), Reports (preview)
- [x] 12B.4.6 Watchlist page (new), Settings and Help pages
- [x] 12B.4.7 Landing page, login and register in the new style
- [x] 12B.4.9 Profile picture (your request 2026-11-24): `PUT/GET/DELETE /api/auth/me/avatar`, new `user_avatars` collection (validator, unique index), upload re-encoded by Pillow to a 256 px WebP without metadata, 5 MB and 40 MP limits, `RATE_LIMIT_AVATAR`; Settings: choose or drop an image, square preview, save or remove; picture shown in the top bar and profile menu (initials otherwise); `tests/test_avatar.py`
- [x] 12B.4.8 Landing page redesign, second pass (your request 2026-11-24): hero with the live NIFTY 50 / SENSEX card (public `/api/market/indices`, falls back to a labelled excerpt of a real run), floating traced number and run progress cards with pointer parallax, sources strip, "trace any number", scroll story of the agents, "explore a real report" tabs (returns, risk, fundamentals, portfolio with backtest), evidence band. Figures come from `src/landing/snapshot.json`, written by `backend/scripts/make_landing_snapshot.py` from a stored run; charts are small SVGs (no chart library on the landing page); no new dependencies

### 12B.5 Quality
- [x] 12B.5.1 Both themes checked in Edge (Playwright) at 1920, 1440, 1366, 1024, 768, 390 and 360px on 14 pages: no overflow, theme applied, no console errors (fixed: landing glow, workflow row at 1024px, index cards at 360px)
- [x] 12B.5.2 Keyboard navigation (skip link, visible focus on every control), Ctrl+K palette with focus inside and Escape, ARIA on tabs/menus/dialogs, reduced motion
- [x] 12B.5.3 444 backend tests pass (after profile pictures), lint 0 errors, build OK; main bundle 128 KB gzip, `motion` (56 KB gzip) loaded only in the signed-in app

### 🛑 Phase 12B Approval Gate
- [x] Phase 12B completion summary posted in chat
- [x] Developer approval received (2026-11-24, after the landing redesign, footer changes and profile pictures)

---

## Phase 13 — Testing, Performance & Optimization

**Objective:** Prove correctness, stability and that the app fits within 8 GB RAM.
**Deliverable:** Test suite passing + testing/performance report.

### 13.1 Test Coverage
- [x] 13.1.1 Fill unit test gaps (indicators, ratios, risk, optimization, validation, database utilities)
- [x] 13.1.2 Independent agent tests (inputs, outputs, invalid data, API failures, missing data, LLM failures)
- [x] 13.1.3 Integration tests (LangGraph, MongoDB, FastAPI endpoints)
- [x] 13.1.4 Frontend ↔ backend integration check (manual test script and/or Vitest for key hooks): contract test `test_frontend_contract.py` (all 29 `api.js` calls exist) and a live API + browser run; no Vitest
- [x] 13.1.5 Financial validation: compare metrics with independent reference calculations on fixed historical datasets

### 13.2 Performance Measurement
- [x] 13.2.1 Per-agent execution time
- [x] 13.2.2 LLM inference time (1.7B vs 0.6B)
- [x] 13.2.3 Peak memory (backend + Ollama + browser)
- [x] 13.2.4 Database response times
- [x] 13.2.5 Total analysis completion time (single stock and 5-stock portfolio)

### 13.3 Optimization
- [x] 13.3.1 Fix identified bottlenecks (caching, fewer LLM calls, smaller context): benchmark reading states the gap, strict answer schemas (18/18 answers accepted, was 11/18), no model swap mid-run
- [x] 13.3.2 Edge-case hardening based on test findings: backtest return from the invested amount, statement periods sorted, 500 errors keep request ID and CORS headers, template observations cover every stock
- [x] 13.3.4 Report key observations: reject an observation that attaches a fact to the wrong stock (found 2026-11-23: the 0.6B model wrote "RELIANCE.NS: the financial statements look solid overall", but "solid" was TCS.NS's rating; RELIANCE.NS was "mixed"), and require at least one observation per stock for 2-5 stocks; a rejected answer goes through the usual retry -> fallback model -> template path; add tests (deferred from the Phase 10 review at your request)
- [x] 13.3.5 Market explanation: check that a stated gap to the NIFTY 50 ("underperformed/outperformed ... by X") matches the computed difference (found 2026-11-23: the 0.6B model wrote "TCS underperformed the NIFTY 50 by 18.31%", but -18.31% is TCS's own 1-year return; the gap is 16.33 points: -18.31% vs -1.98%). The number guard accepts it because 18.31 is in the facts; a rejected answer goes through retry -> fallback model -> template; add tests (deferred from the Phase 10 review at your request)
- [x] 13.3.3 Write the test report → `docs/testing_report.md`

### 🛑 Phase 13 Approval Gate
- [x] Phase 13 completion summary posted in chat
- [x] Developer approval received (2026-11-25; model choice: option 1, `LLM_MIN_FREE_RAM_MB=3000` in `backend/.env` and `.env.example`)

---

## Phase 14 — Final Documentation & GitHub Finalization

**Objective:** Produce complete academic and professional documentation, maintained on GitHub (no live hosting).
**Deliverable:** Polished repository and documentation package.

### 14.1 Documentation
- [ ] 14.1.1 - Create a complete, detailed, and visually stunning `README.md` for NeuralVest with a premium, professional fintech-inspired design.
- Include an attractive header, project overview, features, technology stack, architecture, installation, configuration, usage instructions, and API documentation.
- Add actual website screenshots covering all major modules in both light and dark themes, organized into attractive image layouts.
- Include professional system architecture, multi-agent workflow, data flow, and database diagrams using Mermaid or high-quality SVG/PNG images.
- Ensure the README is GitHub-friendly, easy to navigate, interactive through clickable contents and collapsible sections, well-formatted, accurate, and free from fabricated information.
- [ ] 14.1.2 System architecture diagram
- [ ] 14.1.3 Agent workflow (LangGraph) diagram
- [ ] 14.1.4 Database schema diagram
- [ ] 14.1.5 `docs/api_documentation.md` (+ exported OpenAPI JSON)
- [ ] 14.1.6 `docs/setup_guide.md` final version (Windows installation guide)
- [ ] 14.1.7 Application screenshots `[!] manual review`
- [ ] 14.1.8 Project presentation outline/deck
- [ ] 14.1.9 Final project report
- [ ] 14.1.10 add tasks.md to gitignore and remove comments from env.example and only keep necessary comments

### 14.2 GitHub Finalization
- [ ] 14.2.1 Choose a license for the repository `[!] your decision` (no AGPL constraint, since pypdf replaced PyMuPDF; check the licenses of the remaining dependencies)
- [ ] 14.2.2 Final secret scan of the git history
- [ ] 14.2.3 Clean up branches; merge to `main`
- [ ] 14.2.4 Tag release `v1.0.0` with release notes
- [ ] 14.2.5 Repository description, topics and README badges

### 🛑 Phase 14 Approval Gate (Project Complete)
- [ ] Final completion summary posted in chat
- [ ] Developer approval received

---

## Manual Actions Required From You (running list)

| When | Action | Status |
|------|--------|--------|
| Done | Review and approve `tasks.md` | `[x]` |
| Done | Answer decisions D1–D4 | `[x]` |
| Done | Final Phase 0 approval | `[x]` |
| Phase 8 | Enter the risk-free rate value, date and source in `.env` | `[x]` 5.8602%, RBI 2026-11-18 |
| Phase 1 | Install Python, Node.js, Git, Ollama (if missing); pull Qwen3 models | `[x]` done |
| Phase 1 | Close heavy apps (Chrome, ChatGPT, WhatsApp, extra VS Code windows) so the memory measurement is representative | `[x]` |
| Phase 6 | View the dashboard in a browser (task 6.3.7) | `[x]` |
| Every analysis run | Close heavy background apps so peak RAM stays near the 6.5 GB target | ongoing |
| Phase 1 | Create the GitHub repository and authenticate Git (HTTPS token or SSH) | `[x]` repo created; authentication on first push |
| Phase 2 | Create the MongoDB Atlas M0 cluster, database user and IP allowlist; put the URI in `.env` | `[ ]` |
| Phase 2 | Dedicated `neuralvest_app` Atlas user | `[x]` not needed: you chose to keep the existing user |
| Phase 3 | (Optional) Download annual-report PDFs manually if automated NSE/BSE access is not permitted | `[ ]` |
| Phase 11 | Generate a local JWT secret and put it in `.env` | `[ ]` |
| Phase 14 | Choose the repository license; review screenshots | `[ ]` |

---

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-11-23 | Phases reordered (LLM before agents; MVP dashboard before Agents 3–5) | Needed to meet the Section 19 first milestone |
| 2026-11-23 | Live hosting/deployment excluded; GitHub only | Your project constraint |
| 2026-11-23 | Sequential agent execution by default; parallel mode only behind a config flag | Stability on 8 GB RAM |
| 2026-11-23 | No codebase inspection step; the project is built from scratch | The project folder is empty (your clarification) |
| 2026-11-23 | Existing `docs/` contents are kept unchanged; the folder is created only because Section 15 requires it | Your clarification |
| 2026-11-23 | `docs/` did not exist, so it was created (task 0.1.0) | Required by Section 15 |
| 2026-11-23 | **Approved:** Python 3.12 (D2); Node 26 LTS | Wheel availability; cvxpy needs ≥3.11 |
| 2026-11-23 | **Approved:** custom pandas/NumPy indicators instead of pandas-ta (D3) | pandas-ta appears unmaintained; NumPy 2 issues |
| 2026-11-23 | **Decided:** pypdf replaces PyMuPDF (D1) | Avoids AGPL licensing complications |
| 2026-11-23 | **Approved:** risk-free rate set manually in `.env` in Phase 8; value, date and source recorded in every risk/portfolio result (D4) | Reproducible Sharpe ratios |
| 2026-11-23 | `agent_results` is the source of truth; other collections hold references or write-once projections | Avoid competing versions (review item 1) |
| 2026-11-23 | Never-null `scope_key` in the `agent_results` unique index | MongoDB unique indexes treat null and missing as the same value (review item 2) |
| 2026-11-23 | Restart: re-queue `queued`, mark `running` as `interrupted`, keep `status_history` | No silent loss of job status (review item 3) |
| 2026-11-23 | `$jsonSchema` validators + least-privilege DB user + integrity check | Protect against writes that bypass Pydantic (review item 4) |
| 2026-11-23 | Memory target: ≤ 6.5 GB peak, ≥ 1.5 GB headroom; default model chosen from Phase 1 measurements | 8.5 GB upper estimate exceeded physical RAM (review) |
| 2026-11-23 | Proposed: pwdlib (Argon2) + PyJWT for auth; ReportLab for PDF export; slowapi for rate limiting | passlib unmaintained; ReportLab is BSD and needs no browser engine |
| 2026-11-23 | Proposed: single-worker ThreadPoolExecutor for background workflows | Bounded RAM; no Redis/Celery |
| 2026-11-23 | Proposed: no TTL indexes initially; retention via clean-up of old market data | No collection genuinely requires expiry |
| 2026-11-23 | No automated NSE/BSE scraping; fundamentals from yfinance + manually downloaded PDFs | NSE Terms of Use prohibit automated data collection |
| 2026-11-23 | Python 3.12.10 installed per-user (last 3.12 Windows installer); not on PATH | Keep D2 without disturbing existing 3.11/3.13 |
| 2026-11-23 | Keep Node 22.19.0 instead of upgrading to 26 | Your decision; supported to April 2027 |
| 2026-11-23 | Indicators computed on a 2-year lookback; return/benchmark/volume on the 1-year window | SMA200 + EMA/RSI/MACD warm-up; tiles and charts must show identical values |
| 2026-11-23 | Orchestration: sequential by default; supervisor retries only temporary source failures (once, within a 15-min budget); AI text that contradicts a rule-based reading is rejected like an invented number; the report's numbers must trace to agent outputs; checkpoints optional and off | Reliability on 8 GB RAM; no silent errors |
| 2026-11-23 | Portfolio: 252-day estimation window for live weights and every backtest rebalance; max Sharpe falls back to min volatility when no stock beat the risk-free rate; explicit infeasible caps are errors, default caps are raised to 1/n; HRP implemented in-house (SciPy 1.18 incompatibility) | Backtest tests the real rule; honest, explicit fallbacks |
| 2026-11-23 | Risk: simple daily returns of adjusted close, 252-day annualisation, sample std, beta on common dates, Sharpe on arithmetic annualised return, equal weights until Phase 9; documented thresholds | Standard, reproducible conventions |
| 2026-11-23 | Fundamentals: trailing-annual ratios from Yahoo annual statements; ROE/ROA on average equity/assets; simple documented thresholds; banks: current ratio/operating margin not applicable, debt-to-equity not assessed | Free data source; transparent rules a beginner can follow |
| 2026-11-23 | LLM output guard extended: text with prompt markup or under 20 characters is rejected | Live run returned a digest that was just "<article>" |
| 2026-11-24 | Auth: Argon2id + HS256 JWT bearer tokens (no cookies, so no CSRF); `AUTH_REQUIRED=false` until the Phase 12 login pages; other users' resources answer 404; rate limits with the `limits` library (slowapi's engine) as a dependency, in memory | Keeps the MVP dashboard usable; no Redis; does not reveal which ids exist |
| 2026-11-24 | PDF generated on request from the stored report (not saved to `data/exports/`); charts with ReportLab graphics; Arial for the rupee sign, "Rs" without it | Always matches the stored report; no extra disk use or dependencies |
| 2026-11-24 | Phase 12 design: graphite surfaces + one blue accent (not navy), solid hero text (unslop over the landing skill's gradient text), watchlist as a field on `users`, primary CTA "Create a free account" | Your answers; both skills ask for neutral surfaces |
| 2026-11-24 | Phosphor icons and Geist fonts installed from npm (served locally, not from a CDN); lucide removed | Landing skill icon list; works offline |
| 2026-11-24 | `AUTH_REQUIRED` default changed to `true` now that login pages exist | Reports are private; login is required for analyses |
| 2026-11-23 | A Fundamentals card added to the MVP dashboard now (full Stock Analysis page stays in Phase 12) | Lets you check Phase 7 results in the browser |
| 2026-11-23 | UI review fixes (your screenshots): month-start axis ticks, fitted price axis, "pts" label, split detection by one-day jump (INFY dividends were falsely flagged), Python **key readings** shown above the AI explanation, no LLM digest for a single article | The 0.6B model inverted a reading even when given the correct one; the rule-based readings are the reliable source |
| 2026-11-23 | GDELT is opt-in in the dashboard (checkbox) | Adds ~35 s per analysis and is often rate-limited; RSS alone sometimes finds nothing |
| 2026-11-23 | Technical indicators use the unadjusted close; returns/benchmark use the adjusted close; splits flagged | Matches what price charts show while keeping returns correct |
| 2026-11-23 | News relevance: Python caps the model's label ('high' only if the company is in the headline) | The 0.6B model over-rated passing mentions (Phase 4 test) |
| 2026-11-23 | **Adaptive LLM setup (option 3):** primary `qwen3:1.7b`, fallback `qwen3:0.6b`, `LLM_MIN_FREE_RAM_MB=1800`; replaces the 0.6B-only default from 1.4.5 | Your choice after the Phase 4 comparison: 1.7B quality when RAM allows |
| 2026-11-23 | Every LLM call returns a result: model → retry → fallback model → deterministic template (sentiment `uncertain`, never guessed) | Agents must never fail or invent content because the LLM failed |
| 2026-11-23 | Keep the existing Atlas database user (no dedicated `neuralvest_app` user) | Your decision; it has the permissions the app needs (incl. `collMod`); credentials only in local `.env` |
| 2026-11-23 | Price rows with missing values are removed, never forward-filled | Filled prices would look like real data |
| 2026-11-23 | Test fixtures are synthetic; real Yahoo data is not committed | Yahoo terms restrict redistribution |
| 2026-11-23 | GDELT is a best-effort source; RSS is primary | GDELT rate-limits frequently and is slow (~25 s) |
| 2026-11-23 | Curated news aliases (RIL, HUL, L&T, SBI, …) in `seed_symbols.json`; tickers match case-sensitively | Headlines use abbreviations; case-insensitive tickers matched other companies (Reliance Power) |
| 2026-11-23 | `STORAGE_RESERVED_MB=10` | 11 other databases use ~3.3 MB storage (Atlas UI); margin for their indexes |
| 2026-11-23 | Existing Atlas free cluster reused (shared with `inboxflow`); `STORAGE_RESERVED_MB` setting added to the storage guard | Your choice; NeuralVest cannot measure other projects' storage |
| 2026-11-23 | Routes obtain the DB inside the handler, not via a FastAPI dependency | Dependencies run before parameter validation; invalid input must give 422, not 503 |
| 2026-11-23 | Default LLM = `qwen3:0.6b`; 1.7B opt-in | Phase 1 measurements: baseline RAM already above 6.5 GB |
| 2026-11-23 | Branching: `main` + `phase-N-<topic>` branches merged after approval; Conventional Commits | Approved by you |
| 2026-11-23 | Frontend linting uses oxlint (Vite 8 template default) | Faster, zero-config; ESLint not needed |
| 2026-11-23 | Note: installed yfinance is 1.8.0 and pandas is 3.1 (newer than assumed in architecture §8.1) | Check the yfinance API and pandas 3 Copy-on-Write behaviour in Phase 3 |

## Known Risks & Limitations (checked in Phase 0; details in `docs/architecture.md` §11)

- yfinance is an **unofficial** Yahoo Finance wrapper: data may be delayed or incomplete, it can break when Yahoo changes, and its terms restrict usage. It is not real-time exchange data.
- NSE/BSE websites use bot protection, and automated scraping may break their terms. Fundamentals may need yfinance plus manually downloaded filings.
- Coverage and freshness of Indian company news in GDELT and RSS vary.
- The MongoDB Atlas M0 tier has storage and throughput limits, so market data needs a retention strategy.
- Qwen3 1.7B/0.6B on CPU is slow and limited in reasoning, so the LLM is used only for summaries and explanations.
- RAM is tight. The standard profile (1.7B model) may exceed the ≤ 6.5 GB target on some machines; Phase 1 measurements decide the default model.
- Atlas's 512 MB covers documents and indexes. Heavy repeated portfolio runs could approach it, so storage guards and monitoring are planned.
- All outputs are **educational and illustrative**, not regulated investment advice.

---

## Change History

| Date | Change |
|------|--------|
| 2026-11-23 | Initial task plan created; nothing implemented yet |
| 2026-11-23 | Revision 1: removed the codebase inspection step (empty folder); added the `docs/` folder rule (task 0.1.0, task 1.2.1 updated). No change to scope. |
| 2026-11-23 | Plan approved. Phase 0 executed: created `docs/`, wrote `architecture.md`, `database_design.md`, `setup_guide.md`; all Phase 0 tasks marked complete pending gate approval. |
| 2026-11-23 | Phase 0 Revision 2: applied developer review (source of truth, `scope_key`, job recovery, DB validators, storage estimate, memory target, D1–D4); added section 0.6 and the follow-up tasks in Phases 1, 2, 3, 4, 6, 8, 14. Phase 0 still awaiting approval. |
| 2026-11-23 | Phase 10 approved and merged into `main`. Paused before Phase 11. |
| 2026-11-23 | Phase 10 review: key-observation stock mix-up recorded as task 13.3.4 at your request (no code change). |
| 2026-11-23 | Phase 10 review: wrong NIFTY 50 gap in the AI market explanation recorded as task 13.3.5 at your request (no code change). |
| 2026-11-23 | Phase 10 completed on `phase-10-orchestration`: supervisor (validation, routing, retries, output validation, contradiction guard), parallel mode, optional checkpoints, unified report with glossary and number tracing, report endpoint, dashboard report card, 360 tests, live 5-agent run. Awaiting approval. |
| 2026-11-23 | Phase 9 approved and merged into `main`. Market-text contradiction check deferred to 10.1.5 at your request. Phase 10 started on `phase-10-orchestration`. |
| 2026-11-23 | Phase 9 completed on `phase-9-portfolio`: optimisation + walk-forward backtest modules, Portfolio Optimization Agent, graph branch, runner/projection, 3 portfolio endpoints, dashboard Portfolio card, 326 tests, live 3-stock run cross-checked with SciPy. Awaiting approval. |
| 2026-11-23 | Phase 8 approved (risk-free rate 5.8602%, RBI 2026-11-18) and merged into `main`. Phase 9 started on `phase-9-portfolio`. |
| 2026-11-23 | Phase 8 completed on `phase-8-risk`: risk metrics, Risk Assessment Agent, graph/runner/API, `POST /api/risk/analyze`, dashboard Risk card, 284 tests, live RELIANCE + TCS. Awaiting approval and the risk-free rate. |
| 2026-11-23 | Phase 7 approved and merged into `main`. Work paused before Phase 8 at your request. |
| 2026-11-23 | Phase 7 completed on `phase-7-fundamentals`: fundamentals module, Stock Analysis Agent, graph/runner/API integration, dashboard card, 254 tests, live RELIANCE + HDFCBANK. Awaiting approval. |
| 2026-11-23 | Phase 6 approved and merged into `main`. Work paused before Phase 7 at your request. |
| 2026-11-23 | Phase 6 completed on `phase-6-mvp`: background runner with recovery/re-run, analysis/stocks/news endpoints, React MVP dashboard, real-data indicator verification, strict milestone check, 219 tests. Awaiting your UI check and approval. |
| 2026-11-23 | Phase 5 completed on `phase-5-agents`: indicators, Market Research + Financial News agents, LangGraph workflow, 208 tests, live RELIANCE.NS run. Fixed a Phase 2 test-isolation bug (shared MongoClient closed by another fixture). Awaiting approval. |
| 2026-11-23 | Phase 4 completed on `phase-4-llm`: shared Ollama client, guards, prompts, live 0.6B vs 1.7B comparison; 164 tests. Awaiting approval. |
| 2026-11-23 | Phase 3 completed on `phase-3-data`: symbols, cache, validator, prices, news, financials, PDF text; 133 tests; 5-symbol live run; 30 symbols seeded. Awaiting approval. |
| 2026-11-23 | Phase 2 completed on `phase-2-backend`: FastAPI core, database layer (models, validators, indexes, repository, integrity, retention), health + stock placeholder routes, 64 tests, scripts. Awaiting approval. |
| 2026-11-23 | Phase 1 completed: measurements recorded, default model `qwen3:0.6b`, GitHub remote configured and `main` pushed. Awaiting approval. |
| 2026-11-23 | Phase 0 approved. Phase 1 started: Python 3.12.10, venv + backend packages, Vite/React/Tailwind frontend, Ollama settings + Qwen3 models, env templates, `.gitignore`/`.gitattributes`, README, measurement script, local git repo. |
