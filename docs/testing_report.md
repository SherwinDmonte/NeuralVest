# NeuralVest Testing and Performance Report

Phase 13 (tasks 13.1 to 13.3). Measured on 25 November 2026 on the development laptop.

Every number in this report was produced by the test suite or by `backend/scripts/measure_performance.py`;
the raw results are in `data/exports/performance_*.json` (not committed). Section 6 lists what was found
and fixed, and section 7 what remains open.

---

## 1. Test environment

| Item | Value |
|---|---|
| Machine | Windows 11 Home, 12 logical CPUs, no graphics card used, 7.68 GB RAM visible to Windows |
| Free RAM during the measurements | 0.8 to 1.9 GB (VS Code and the usual background programs open) |
| Python / key packages | Python 3.12.10, pandas 3.1.1, NumPy 2.5.5, SciPy 1.18.1, PyPortfolioOpt 1.6.0, LangGraph 1.2.24 |
| LLM | Ollama with `qwen3:1.7b` (primary) and `qwen3:0.6b` (fallback), `num_ctx` 2048, thinking off |
| Database | MongoDB Atlas free tier, the separate test database (`*_test`) only |
| Browser | Microsoft Edge (headless, driven by Playwright) |

---

## 2. Test suite

```text
python -m pytest            -> 544 passed (3 minutes)
python -m pytest --cov=app  -> 94% of statements covered
```

| Area | Test files | Tests |
|---|---|---|
| Calculations (indicators, risk, optimisation, backtest, fundamentals) | `test_technical_indicators`, `test_risk_metrics`, `test_optimization`, `test_backtesting`, `test_fundamentals` | 84 |
| Financial validation on real data (13.1.5) | `test_financial_validation` | 42 |
| Data collection and validation | `test_stock_data`, `test_financial_data`, `test_news_data`, `test_data_validator`, `test_symbols`, `test_cache`, `test_pdf_text` | 71 |
| Agents (13.1.2) | `test_agent_*` (five files) | 56 |
| LLM client, prompts and output guards | `test_llm_client`, `test_llm_prompts`, `test_llm_guards`, `test_llm_guards_phase13` | 67 |
| Workflow and orchestration (LangGraph) | `test_graph`, `test_workflow`, `test_supervisor`, `test_analysis_runner` | 53 |
| API, authentication, reports, PDF | `test_api`, `test_api_phase11`, `test_auth_security`, `test_market`, `test_avatar`, `test_pdf_export` | 89 |
| Failure paths (13.1.1 to 13.1.3) | `test_failure_paths` | 22 |
| Database (integration, 13.1.3) | `test_database_integration`, `test_models`, `test_retention`, `test_config`, `test_logging` | 57 |
| Frontend and backend contract (13.1.4) | `test_frontend_contract` | 3 |

62 tests are integration tests that use the Atlas test database. They are skipped when MongoDB is not
configured. The 42 financial validation tests are skipped until the fixed dataset has been created once
(section 3).

**Coverage.** Statement coverage went from 93% to 94%. The lowest files before Phase 13 were now covered:
`stock_data` 69% to 98% (Yahoo rate limits, network errors, empty and changed responses), `financial_data`
77% to 97%, the health routes 79% to 94% (database and Ollama unavailable) and `schema_validators` 78% to
100% (a database user without the dbAdmin role, as used by this project).

### 2.1 Agent tests (13.1.2)

Each agent is tested on its own, with synthetic prices and fixture data, for: a normal run, invalid input
(bad symbol, invalid amount or constraints), missing data (no prices, no statements, no benchmark, short
history), data source failures (all news sources down), and the LLM being absent (the rule based template
is used and labelled). Phase 13 added the case of **Ollama failing in the middle of a run**: the real client
with a transport that refuses every connection, times out, or returns HTTP 500. In all three cases every agent
finished with its template, no news sentiment was guessed, the portfolio was still allocated, and the
report was built with every number traced.

### 2.2 Integration tests (13.1.3)

* **LangGraph:** the full graph on one and several stocks, invalid input, partial failures, retries and the
  output validation node (`test_graph`, `test_workflow`, `test_supervisor`).
* **MongoDB:** validators, indexes, uniqueness, retention and the analysis runner's job records, against the
  test database (`test_database_integration`, `test_analysis_runner`).
* **FastAPI:** every route group, the error envelope, rate limits, authentication and ownership rules.
  Phase 13 added tests for the global error handlers (section 6.4).

### 2.3 Frontend and backend (13.1.4)

* **Contract test.** `test_frontend_contract.py` reads every call in `frontend/src/services/api.js` (29
  endpoints) and checks that the API serves that path with that method, using FastAPI's OpenAPI schema.
  All 29 exist. A renamed route, or a frontend call to a route the API does not have yet (the "Not Found"
  seen in Phase 12B when the running API was older than the frontend), now fails a test instead.
  Four routes are not used by the web app and serve Swagger and scripts only: `GET /api/analysis/{id}/report`,
  `GET /api/portfolio/{id}`, `GET /api/stocks/{symbol}` and `POST /api/portfolio/backtest`.
* **Live check.** With the API (test database, login required) and the Vite server running, a script
  registered a user, started a five stock portfolio analysis through `POST /api/analysis/start`, polled it
  to the end (298 s, status partial for the reason in section 4.4) and opened all ten pages and the finished
  report in Edge. No page reported a JavaScript error.

---

## 3. Financial validation (13.1.5)

**Dataset.** `scripts/freeze_validation_dataset.py` saved real daily prices for RELIANCE, TCS, INFY,
HDFCBANK and the NIFTY 50 (25 Nov 2024 to 20 Nov 2026, 494 trading days; 493 for the index) and the FY2026
annual statements of RELIANCE, TCS and HDFCBANK, all from Yahoo Finance. The files are kept in
`data/historical/validation/` and are not committed, because Yahoo data is not redistributed. A manifest of
SHA-256 hashes makes the tests fail if the data changes.

**Method.** Each metric is recomputed by an independent reference written from its textbook definition:
plain Python loops, or NumPy and SciPy where a loop is impractical. The references do not use pandas
rolling or ewm, PyPortfolioOpt, cvxpy or scikit-learn, which the production code uses. The production
values are rounded, so each one must match the reference to within half a unit of its last digit.

| Metric | Reference | Result |
|---|---|---|
| SMA 20/50/200, EMA 12/26, RSI 14 (Wilder), MACD and signal, Bollinger bands | Plain loops | Equal to 1e-8 on all 5 series |
| Period return and NIFTY 50 comparison | Loop on common dates | Equal |
| Daily returns, annualised volatility and mean, skewness, excess kurtosis, Sharpe ratio | Loops; sample skewness and kurtosis formulas | Equal |
| Beta and correlation with the NIFTY 50 | Covariance and variance loops on common dates | Equal |
| Maximum drawdown with peak, trough and recovery dates | Loop with a running peak | Equal, dates identical |
| Correlation matrix, concentration (HHI) | Pairwise loops | Equal |
| Expected returns, sample and Ledoit-Wolf covariance | NumPy, Ledoit and Wolf (2004) written from the paper | Equal to 1e-8 |
| Minimum volatility weights, two windows and two weight limits | SciPy SLSQP | Same volatility (1e-6), weights within 0.5 points |
| Maximum Sharpe weights, two weight limits | SciPy SLSQP | Same Sharpe ratio (1e-4), weights within 1 point |
| Backtest equity curve, quarterly rebalancing, 10 bps costs | Share based simulation | Equal to 1e-10 |
| Backtest return, CAGR and volatility | From the reference curve | Equal after the fix in 6.2 |
| ROE, ROA, margins, debt to equity, current ratio, EPS, P/E, P/B, revenue growth and CAGR | Formulas on the raw statement items | Equal after the fix in 6.3 |

In the latest year of the dataset no stock's average return beat the risk-free rate, so maximum Sharpe is not
defined. The test confirms that the documented fallback (minimum volatility, reported with its reason) is used.
The maximum Sharpe comparison uses the first year, in which two stocks beat the rate.

---

## 4. Performance (13.2)

### 4.1 LLM inference, 1.7B against 0.6B (13.2.2)

Three runs of each of three real prompts per model, through the production client with every output check
active. "Accepted" means the answer passed all checks; a rejected answer is retried with a repair hint and
finally replaced by the template.

| Prompt | `qwen3:1.7b` median (max) | `qwen3:0.6b` median (max) | Accepted, 1.7B / 0.6B |
|---|---|---|---|
| Market explanation | 7.1 s (14.7 s) | 5.4 s (7.5 s) | 3/3 / 3/3 |
| News article analysis | 3.2 s (6.7 s) | 1.5 s (2.9 s) | 3/3 / 3/3 |
| Key observations (two stocks) | 10.4 s (17.3 s) | 6.0 s (9.1 s) | 3/3 / 3/3 |
| Generation speed | 15 to 16 tokens/s | 31 to 35 tokens/s | |
| Model load and first answer | 7.2 s | 5.1 s | |
| Ollama RAM while answering | 1.5 to 1.7 GB | 0.92 to 0.95 GB | |

**Before the prompt fixes in section 6.1**, with the same prompts and checks, the market explanation was
accepted 2 of 3 times on 1.7B (13 to 21 s with retries) and 0 of 3 times on 0.6B, and the key observations 0 of
3 times on 1.7B (20 s per attempt, then the template). In total 11 of 18 answers were accepted then, and 18 of
18 after.

### 4.2 Total analysis time (13.2.5) and per-agent time (13.2.1)

The workflow runs as it does in the app (adaptive model choice, prices from the cache when fresh, GDELT
off), measured during NSE trading hours.

| Run | Total | Market research | News | Stock analysis | Risk | Portfolio | Report |
|---|---|---|---|---|---|---|---|
| 1 stock (RELIANCE), 0.6B throughout | **58.6 s** | 14.6 s | 28.8 s | 4.8 s | 4.7 s | | 5.7 s |
| 5 stocks + portfolio, 0.6B throughout | **248.7 s** | 61.4 s | 100.4 s | 22.4 s | 23.8 s | 17.7 s | 23.0 s |
| 5 stocks + portfolio, through the API and browser | 297.8 s | | | | | | |
| *Before 6.5:* 1 stock, 1.7B loaded for the first call | 109.1 s | 31.2 s | 55.8 s | 6.0 s | 6.9 s | | 9.3 s |
| *Before 6.5:* 5 stocks, 1.7B loaded for the first call | 629.5 s | 223.1 s | 317.3 s | 21.6 s | 22.3 s | 12.1 s | 33.1 s |

News analysis is the largest part: up to 8 articles per stock, each one LLM call, plus a digest. Most time is
LLM inference; the calculations themselves take well under a second per stock.

### 4.3 Peak memory (13.2.3)

| Process | Measured peak | Phase 0 estimate (architecture §10.2) |
|---|---|---|
| Backend Python code (whole workflow in one process) | 203 to 217 MB | 0.3 to 0.6 GB |
| Ollama with `qwen3:0.6b` | 0.92 to 1.08 GB | 0.9 to 1.5 GB |
| Ollama with `qwen3:1.7b` | 1.50 to 1.75 GB | 1.8 to 2.5 GB |
| Browser (Edge), private memory after three tours of every page | 0.52 GB (0.39 GB at the start; levels off, no leak) | 0.3 to 0.6 GB |
| **Whole system during a run** | **7.50 to 7.62 GB in use, 240 to 362 MB free** | target ≤ 6.5 GB in use, ≥ 1.5 GB free |

NeuralVest's own processes stay within their estimates (about 1.7 GB with 0.6B, 2.4 GB with 1.7B, against
a 3.5 GB budget). **The whole-system target is not met on this laptop**: with VS Code and the background
programs open, Windows already used about 6 GB before the analysis started. Section 7.1 has the consequence
for the model choice.

### 4.4 Database response times (13.2.4)

20 runs each against MongoDB Atlas (free tier), after one warm-up call.

| Operation (as the API does it) | Median | 95th percentile |
|---|---|---|
| Ping | 4.2 ms | 5.6 ms |
| One report by `request_id` (indexed) | 7.5 ms | 9.9 ms |
| Report list, 20 newest, without the report body | 5.4 ms | 7.3 ms |
| Agent results of one analysis | 5.5 ms | 7.3 ms |
| One year of daily prices for one stock | 21.8 ms | 27.6 ms |
| Status update of a running analysis | 8.4 ms | 10.7 ms |

The database is not a bottleneck: all database work in an analysis takes well under a second.

The five-stock runs ended with status *partial* for a documented reason, not an error. On 3 of 5 backtest
rebalance dates the maximum Sharpe problem could not be solved under the 35% weight limit, so equal weights
were used for those dates and the report says so (Phase 9 rule).

---

## 5. Output checks against real model answers (13.3.4, 13.3.5)

Two mistakes were recorded in the 23 November live runs. The new checks reject them and send the answer
through the usual path (retry with the reason → fallback model → rule based template).

| Check | Rejects | Example from a real answer |
|---|---|---|
| Gap to the NIFTY 50 | A stated gap that is not the computed difference | "TCS underperformed the NIFTY 50 by 18.31%" (−18.31% is TCS's own return; the gap is 16.33 points) |
| Fact attached to the wrong stock | A label or figure of another stock in a sentence about one stock | "RELIANCE.NS: the financial statements look solid overall" ("solid" was TCS's rating) |
| Every stock mentioned (2 to 5 stocks) | Observations that leave a stock out | qwen3:1.7b wrote TCS's observations outside the list (Phase 13 benchmark) |
| Own readings per stock | A sentence that contradicts that stock's own reading | |

The gap check fired on almost every answer of both models in the first benchmark. That showed the models
copy a pattern ("outperformed by" followed by the stock's own return) rather than the figures. The fix
(section 6.1) was in the prompt input, not in the checks.

---

## 6. Problems found and fixed

### 6.1 The models misstated the gap to the NIFTY 50 (optimisation 13.3.1)
The benchmark reading said "outperformed the NIFTY 50 over the period (4.12% for the stock vs −1.98% for the
NIFTY 50)". Both models rewrote it as "outperformed the NIFTY 50 by 4.12%". The reading now states the
computed gap right after the verb: "outperformed the NIFTY 50 by 6.1 percentage points over the period
(4.12% for the stock vs −1.98% for the NIFTY 50)". In addition, every answer schema now forbids keys the
schema does not define (`additionalProperties: false`, which Ollama enforces as a grammar), so a model cannot
put content outside the expected fields. Result: 18 of 18 answers accepted instead of 11, and the median
1.7B market explanation fell from 13 to 21 s to 7 s because no retries were needed.

### 6.2 Backtest returns left out the first purchase cost
Total return and CAGR were measured from the value after the first day's 10 bps cost (₹99,900), not from the
₹1,00,000 invested: −17.34% was reported for an actual −17.42%. They are now measured from the invested
amount. *This changes a Phase 9 result slightly (by the cost of the first purchase).*

### 6.3 Fundamentals relied on the order of the statement periods
The ratio code took the first period in a dictionary as the latest year. That holds for data straight from
Yahoo Finance, but a JSON file with sorted keys reverses it, and the code then silently used FY2023 as the
latest year. Periods are now sorted by date. Live reports were not affected.

### 6.4 Unexpected server errors had no request ID and no CORS headers
FastAPI runs a catch-all error handler outside every middleware, so a 500 response had no `X-Request-ID`
(it could not be matched to the log) and no CORS headers (the browser showed a network error instead of the
API's message). A small middleware now answers these errors inside the request ID and CORS middleware.

### 6.5 The model was switched in the middle of every run
The client checked free RAM before each call. Once the 1.7B model was loaded, the RAM it held counted as used,
so every later call switched to 0.6B and Ollama swapped models. In effect the 1.7B model answered once per
analysis, at the highest cost: one call took 141 s while Windows was paging. The RAM held by a loaded primary
model now counts as available to it. Two tests cover both cases.

### 6.6 Smaller fixes
* Template observations (used when the AI text is rejected) now take readings from each stock in turn, so
  every stock appears; before, with five stocks they could cover only two.
* The key observations check is now per stock. The old combined check took the "truth" from the first stock,
  so a correct sentence about a second stock could be rejected as a contradiction.

---

## 7. Open points and limitations

### 7.1 Model choice on this laptop (decision needed)
With VS Code open, loading `qwen3:1.7b` leaves only 240 to 360 MB free and Windows starts paging. The
first-call measurements in 4.2 (109 s and 630 s) show the cost. The switch threshold `LLM_MIN_FREE_RAM_MB`
(1800 MB) is checked before the model is loaded, but loading it needs about 1.5 GB of that. Under the rule in
architecture §10.2 (idle use plus NeuralVest above 6.5 GB means 0.6B becomes the default), this machine
qualifies. Two options:
* raise `LLM_MIN_FREE_RAM_MB` to about 3000, so 1.7B is used only when there is room for it (for example with
  VS Code closed); or
* make `qwen3:0.6b` the primary model in `.env`.

Either keeps the analysis working; the difference is answer quality against speed (architecture §10.3:
1.7B judges news relevance better; section 4.1 here for the speed).

### 7.2 Other limitations
* The performance numbers are from one laptop on one day, during trading hours, with the price cache warm.
  The first analysis of a new stock also waits for Yahoo Finance.
* The financial validation compares two implementations of the same definitions. It does not show that Yahoo
  Finance's data is correct.
* Browser memory was measured in headless Edge; a visible browser window uses more for drawing.
* No Vitest unit tests were added for the React code; the frontend is covered by the contract test and the
  live check.
