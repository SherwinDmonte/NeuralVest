# NeuralVest API

REST API of the NeuralVest backend (FastAPI), version 1.0.0. It runs locally at `http://localhost:8000`;
there is no hosted instance.

* **Interactive documentation:** http://localhost:8000/docs (Swagger UI), http://localhost:8000/redoc
* **Machine-readable schema:** [`openapi.json`](openapi.json) (OpenAPI 3.1). Regenerate it after a route
  change with `python scripts/export_openapi.py` in `backend`; a test fails if it is out of date.

All figures the API returns are computed in Python from public end-of-day data. They are educational and
are not investment advice.

---

## Contents

1. [Conventions](#1-conventions)
2. [Authentication](#2-authentication)
3. [Errors](#3-errors)
4. [Rate limits](#4-rate-limits)
5. [Endpoints](#5-endpoints): [health](#51-health) · [auth](#52-auth) · [stocks](#53-stocks) ·
   [market](#54-market) · [analysis](#55-analysis) · [news](#56-news) · [risk](#57-risk) ·
   [portfolio](#58-portfolio) · [reports](#59-reports)
6. [Running an analysis from start to finish](#6-running-an-analysis-from-start-to-finish)

---

## 1. Conventions

| Item | Rule |
|---|---|
| Base path | `/api` |
| Format | JSON in and out, except the profile picture upload (raw image) and the PDF download |
| Symbols | Yahoo style: `RELIANCE.NS` (NSE) or `500325.BO` (BSE). Inputs such as `RELIANCE` or `500325` are normalised to these. Pattern: `^\^?[A-Z0-9&\-]{1,20}(\.(NS\|BO))?$` |
| Ids | `request_id`, `report_id` and `portfolio_id` are 32 lowercase hex characters |
| Dates | ISO 8601, UTC (`2026-11-20T10:15:00Z`); trading dates as `YYYY-MM-DD` |
| Money | Indian rupees |
| Lists | `page` (from 1) and `page_size` (up to 100) where a list can grow |
| Request ID | Every response has an `X-Request-ID` header (also on errors); send your own (8 to 64 letters, digits, `-` or `_`) to follow a request through the logs |

---

## 2. Authentication

1. `POST /api/auth/register` with a name, email and password (8 to 128 characters).
2. `POST /api/auth/login` returns `access_token`.
3. Send it on later requests: `Authorization: Bearer <access_token>`.

Tokens are JWTs (HS256) that expire after `JWT_EXPIRE_MINUTES` (default 60); log in again afterwards.
Passwords are stored as Argon2id hashes.

* With `AUTH_REQUIRED=true` (the default) analyses, risk, portfolio and report endpoints need a token.
* Your analyses, portfolios and reports are private. Asking for someone else's id answers **404**, the same as an
  id that does not exist, so ids cannot be probed.
* Health, stock, market and news endpoints are public: they serve public market data only.

---

## 3. Errors

Every error has the same shape:

```json
{
  "error": {
    "code": "stock_not_found",
    "message": "No price data for NOTREAL.NS. The symbol may be invalid or delisted.",
    "details": null,
    "request_id": "3f2b9c0e8a7d4c1b9e6f5a4d3c2b1a09"
  }
}
```

`code` is stable and meant for programs; `message` is meant for people. Internal details (stack traces,
database messages) are logged on the server and never returned.

| Status | Codes |
|---|---|
| 401 | `not_authenticated`, `invalid_token`, `token_expired` |
| 404 | `not_found` (no such route), `analysis_not_found`, `stock_not_found`, `financials_not_found`, `avatar_not_found`, `report_not_found`, `portfolio_not_found` |
| 405 | `method_not_allowed` |
| 409 | `email_already_registered`, `report_not_ready`, `not_rerunnable` |
| 413 | `file_too_large` (profile picture over 5 MB) |
| 415 | `unsupported_media_type` (profile picture not JPEG, PNG or WebP) |
| 422 | `validation_error` (`details` lists each field and the reason), `invalid_image`, `portfolio_infeasible`, `backtest_not_possible` |
| 429 | `rate_limited` (with a `Retry-After` header), `queue_full` |
| 500 | `database_error`, `internal_error` |
| 502 | `data_source_unavailable` (Yahoo Finance or a news source failed) |
| 503 | `database_not_configured`, `database_unavailable`, `auth_not_configured` |
| 507 | `storage_limit_reached` (the Atlas free-tier storage guard; `details.used_pct`) |

---

## 4. Rate limits

Counted per user (or per IP address without a login) in a moving window, in memory, so they reset when the
API restarts. Each limit is set in `backend/.env`.

| Group | Default | Endpoints |
|---|---|---|
| `auth` | 10/minute | register, login |
| `analysis` | 5/minute | start and rerun an analysis |
| `portfolio` | 10/minute | portfolio optimise and backtest, risk analysis |
| `pdf` | 20/minute | report PDF |
| `avatar` | 10/minute | profile picture upload |

A limited request answers 429 with `Retry-After` (seconds). `RATE_LIMIT_ENABLED=false` turns them off.

---

## 5. Endpoints

🔒 = needs a token (with `AUTH_REQUIRED=true`).

### 5.1 Health

| Method | Path | What it returns |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "version", "environment"}` |
| GET | `/api/health/db` | MongoDB connection, latency, initialisation result and storage use. 200 when reachable, 503 otherwise (same shape) |
| GET | `/api/health/llm` | Whether Ollama is reachable, the installed models, free RAM, and which model would answer now |

### 5.2 Auth

| Method | Path | Body or parameters | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | `{"name": 1-80 chars, "email", "password": 8-128 chars}` | 201; 409 `email_already_registered` |
| POST | `/api/auth/login` | `{"email", "password"}` | `{"access_token", "token_type": "bearer", "expires_in" (seconds), "expires_at", "user"}` |
| GET 🔒 | `/api/auth/me` | | The logged-in user (`avatar_version` is set when a picture exists) |
| GET 🔒 | `/api/auth/me/watchlist` | | `{"symbols": [...]}` |
| PUT 🔒 | `/api/auth/me/watchlist` | `{"symbols": [...]}`, up to 20 | Symbols are normalised and de-duplicated |
| GET 🔒 | `/api/auth/me/avatar` | | The picture as `image/webp` (256 × 256); 404 `avatar_not_found` |
| PUT 🔒 | `/api/auth/me/avatar` | Raw image body, `Content-Type: image/jpeg`, `image/png` or `image/webp`, up to 5 MB | Cropped to a square, re-encoded as WebP, photo metadata (such as location) removed |
| DELETE 🔒 | `/api/auth/me/avatar` | | Removes the picture |

### 5.3 Stocks

| Method | Path | Parameters | What it returns |
|---|---|---|---|
| GET | `/api/stocks/search` | `q` (required), `limit` (10, up to 50) | Matching symbols from the curated list and analysed companies, best match first |
| GET | `/api/stocks/{symbol}` | | Stored company information |
| GET | `/api/stocks/{symbol}/history` | `period`: `1mo`, `3mo`, `6mo`, `1y` (default), `2y` | Daily OHLCV; fetched from Yahoo Finance and stored if not yet in MongoDB |
| GET | `/api/stocks/{symbol}/indicators` | `period`: `6mo`, `1y` (default) | Close, volume, SMA 20/50/200, EMA 12/26, RSI 14, MACD and Bollinger series, computed on two years so SMA 200 is defined throughout |
| GET | `/api/stocks/{symbol}/financials` | | Annual income statement, balance sheet and cash flow as reported, newest year first |

### 5.4 Market

| Method | Path | Parameters | What it returns |
|---|---|---|---|
| GET | `/api/market/indices` | | NIFTY 50 and SENSEX: last close, day change and a short series |
| GET | `/api/market/breadth` | `top` (5, up to 10) | Gainers, losers, advancers and decliners **across the 30 curated stocks only** (not the whole market). The first call fetches all 30 and can take a minute |
| GET | `/api/market/quotes` | `symbols` (comma separated, up to 20) | Last close, day change and a short series per symbol |

### 5.5 Analysis

An analysis runs the multi-agent workflow in the background (one at a time; others wait in a queue).

| Method | Path | Notes |
|---|---|---|
| POST 🔒 | `/api/analysis/start` | 202. Body below. Returns `{"request_id", "report_id", "status": "queued", "symbols", "status_url"}`. 429 `queue_full` when too many are waiting; 507 when storage is nearly full |
| GET 🔒 | `/api/analysis/{request_id}/status` | `{"status", "symbols", "agents": {agent: state}, "queue_position", "status_history"}`. Poll every 2 to 3 s |
| GET 🔒 | `/api/analysis/{request_id}` | The job and every agent's full output |
| GET 🔒 | `/api/analysis/{request_id}/report` | The unified report; 409 `report_not_ready` while running |
| POST 🔒 | `/api/analysis/{request_id}/rerun` | 202; only for `failed` or `interrupted` analyses (409 `not_rerunnable` otherwise) |

Status values: `queued`, `running`, `completed`, `partial` (some sections could not be computed; the report
says which and why), `failed`, `interrupted` (the API stopped during the run).

```json
POST /api/analysis/start
{
  "symbols": ["RELIANCE", "TCS", "INFY"],
  "include_gdelt": false,
  "investment_amount": 100000,
  "risk_preference": "moderate"
}
```

| Field | Type | Rule |
|---|---|---|
| `symbols` | list of strings | 1 to 10 |
| `include_gdelt` | boolean | Default `false`. GDELT adds news but is slow and often rate-limited |
| `investment_amount` | number | Optional, above 0, up to 1,000,000,000. With 2 or more stocks it adds the Portfolio Optimization agent |
| `risk_preference` | `conservative`, `moderate`, `aggressive` | Default `moderate`; chooses the optimisation method and weight limit |
| `portfolio` | object | Optional overrides: `method`, `constraints` (`min_weight_pct`, `max_weight_pct`) and the other optimisation fields of 5.8 |

### 5.6 News

| Method | Path | Parameters | What it returns |
|---|---|---|---|
| GET | `/api/news/{symbol}` | `sentiment`, `page`, `page_size` (20, up to 100) | Stored, analysed articles (newest first) with sentiment, category, relevance, summary and source link |
| GET | `/api/news/{symbol}/sentiment` | `days` (14, up to 90) | Counts by sentiment over the period |

News is stored by analyses; these endpoints do not fetch new articles.

### 5.7 Risk

`POST /api/risk/analyze` 🔒 — historical risk for one or more stocks, computed on request (several seconds).

| Field | Rule |
|---|---|
| `symbols` | 1 to 10 |
| `period` | `6mo`, `1y` (default), `2y` |
| `weights` | Optional `{symbol: weight}` for the portfolio view (equal weights otherwise) |

Per stock: annualised volatility, beta and correlation with the NIFTY 50, maximum drawdown with dates, Sharpe
ratio (needs the risk-free rate in `.env`), the return distribution and a 21-bin histogram. With several stocks:
correlation matrix, concentration and diversification.

### 5.8 Portfolio

| Method | Path | Notes |
|---|---|---|
| POST 🔒 | `/api/portfolio/optimize` | An illustrative allocation (weights, rupees, whole shares) plus a backtest; saved with a `portfolio_id` |
| POST 🔒 | `/api/portfolio/backtest` | A walk-forward backtest of an allocation rule; nothing is stored |
| GET 🔒 | `/api/portfolio/{portfolio_id}` | A saved allocation |

| Field | Rule |
|---|---|
| `symbols` | 2 to 10 |
| `investment_amount` | Required for optimise: above 0, up to 1,000,000,000 |
| `risk_preference` | `conservative` (min volatility, max 25% per stock), `moderate` (max Sharpe, max 35%), `aggressive` (efficient risk, max 50%) |
| `method` | Optional override: `max_sharpe`, `min_volatility`, `efficient_risk`, `efficient_return`, `equal_weight`, `inverse_volatility`, `hrp` |
| `constraints` | `min_weight_pct` (0 to 100), `max_weight_pct`; short selling is not supported |
| `target_volatility_pct`, `target_return_pct` | For `efficient_risk` and `efficient_return` |
| `returns_model` | `mean` (default) or `ema` |
| `covariance_model` | `ledoit_wolf` (default) or `sample` |
| `rebalance` | `monthly`, `quarterly` (default), `none` |
| `transaction_cost_bps` | 0 to 200, default 10 |
| `backtest` (optimise) | Default `true` |
| `period`, `initial_capital` (backtest) | `2y` (default) or `5y`; default ₹1,00,000 |

A method that cannot be used falls back to a documented one and the response says why (for example, maximum
Sharpe needs a stock whose past return beat the risk-free rate). Constraints no allocation can meet answer 422
`portfolio_infeasible`; too little history answers 422 `backtest_not_possible`.

### 5.9 Reports

| Method | Path | Parameters | What it returns |
|---|---|---|---|
| GET 🔒 | `/api/reports` | `page`, `page_size`, `status`, `symbol` | Your reports, newest first, with status, symbols and the first key observations |
| GET 🔒 | `/api/reports/{report_id}` | | One report with every agent's results |
| GET 🔒 | `/api/reports/{report_id}/pdf` | | The report as a PDF, generated from the stored report on request |

---

## 6. Running an analysis from start to finish

PowerShell, with the API running on port 8000:

```powershell
$api = "http://localhost:8000/api"
$login = Invoke-RestMethod "$api/auth/login" -Method Post -ContentType "application/json" `
  -Body '{"email": "you@example.com", "password": "your password"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }

$job = Invoke-RestMethod "$api/analysis/start" -Method Post -Headers $h -ContentType "application/json" `
  -Body '{"symbols": ["RELIANCE", "TCS"], "investment_amount": 100000}'

do { Start-Sleep 3; $s = Invoke-RestMethod "$api/analysis/$($job.request_id)/status" -Headers $h; $s.status }
while ($s.status -in "queued", "running")

$report = Invoke-RestMethod "$api/analysis/$($job.request_id)/report" -Headers $h
$report.report.key_observations.items
Invoke-WebRequest "$api/reports/$($job.report_id)/pdf" -Headers $h -OutFile report.pdf
```

On this project's 8 GB laptop one stock takes about a minute and five stocks with a portfolio about four
minutes ([testing report](testing_report.md) §4.2).
