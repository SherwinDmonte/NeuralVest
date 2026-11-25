# NeuralVest: Final Project Report

**A multi-agent financial intelligence platform for Indian equities, running on a CPU-only 8 GB laptop with
free tools.**

Author: Sherwin Dmonte · Version 1.0.0 · November 2026 · License: MIT

---

## Abstract

NeuralVest analyses stocks listed on the National Stock Exchange (NSE) and the Bombay Stock Exchange (BSE). Five
specialised agents (market research, financial news, stock analysis, risk assessment and portfolio
optimisation) are coordinated by a LangGraph supervisor and produce one report per request. All figures are
computed in Python from public end-of-day data. A small local language model (Qwen3, 1.7B or 0.6B parameters,
through Ollama) only explains figures it is given, and every explanation is checked before it is shown: invented
numbers, contradictions of the computed readings, a wrong gap to the NIFTY 50 benchmark or a fact attached to the
wrong stock are rejected and replaced. Every number in a report is traced to the agent that computed it.

The system runs on a Windows laptop with 8 GB of RAM and no graphics card, using only free software and the
MongoDB Atlas free tier. On that machine one stock is analysed in about a minute and five stocks with an
illustrative portfolio in about four minutes. The backend has 545 automated tests (94% statement coverage),
including a validation of every financial metric against independent reference calculations on real data.

The project is educational. Its outputs describe the past and are not investment advice.

---

## 1. Introduction

### 1.1 Problem

Retail investors in India can find stock prices, news and annual statements, but combining them takes time and
knowledge: which ratios matter, how risky a stock was, how a group of stocks behaves together. Language models
can summarise such material, but they also state numbers that are wrong with full confidence, which in finance is
worse than no answer. Large models also need hardware or paid services that a student or a retail investor may not
have.

### 1.2 Aim

Build a system that brings these sources together into one understandable report, in which:

* every number is computed by ordinary, testable code, not by the language model;
* the language model only explains, and its text is checked against the computed facts;
* the whole system runs on an ordinary 8 GB laptop at no cost.

### 1.3 Objectives

1. Collect and validate daily prices, annual statements and news for NSE and BSE stocks from free sources.
2. Implement five agents, each with a clear input and output contract, coordinated by a supervisor.
3. Compute technical indicators, fundamental ratios, historical risk, an optimised illustrative allocation and a
   walk-forward backtest, each with its formula and data window.
4. Use a local LLM for explanations only, with guards that reject unsupported or contradictory text.
5. Provide a web application with accounts, saved reports and PDF export.
6. Verify correctness and measure performance and memory within the 8 GB limit.

### 1.4 Constraints

| Constraint | Consequence for the design |
|---|---|
| CPU only, 8 GB RAM | Small quantised models; one model and one analysis at a time; sequential agents by default |
| Zero budget | Open-source software only; MongoDB Atlas free tier (512 MB); free public data |
| No hosting, GitHub only | Everything runs locally; documentation instead of a live demo |
| Data terms | No scraping of NSE or BSE websites; Yahoo Finance data is not redistributed |

---

## 2. Background and tool choice

**Multi-agent orchestration.** LangGraph models the workflow as a state graph: nodes are agents, edges carry a
shared state, and conditional edges let a supervisor decide what runs next. It was chosen over free-form agent
frameworks because the route through the agents should be predictable and testable.

**Local language models.** Qwen3 is available in small sizes (0.6B and 1.7B parameters) under the Apache 2.0
license and runs through Ollama on a CPU. Ollama can constrain the output to a JSON schema, which makes small
models usable for structured tasks. Thinking mode is turned off to save tokens.

**Financial calculations.** pandas and NumPy for the indicators and statistics, SciPy for distribution
statistics, and PyPortfolioOpt with cvxpy for mean-variance optimisation. The technical indicators are
implemented in the project (instead of pandas-ta, which appeared unmaintained) and checked against textbook
definitions.

**Data.** Daily prices and annual statements from Yahoo Finance through the unofficial yfinance library; news from
public RSS feeds of Indian business publications and, optionally, GDELT; the risk-free rate is the RBI 91-day
Treasury bill yield, entered by the user with its date and source.

**Application.** FastAPI and Pydantic for the API, MongoDB Atlas for storage, React with Vite, Tailwind CSS and
Recharts for the web application, ReportLab for PDF export, Argon2id and JWT for authentication.

---

## 3. System design

The diagrams are in [diagrams.md](diagrams.md) and the full design in [architecture.md](architecture.md).

### 3.1 Architecture

The browser talks to a FastAPI backend over REST. An analysis is submitted to a single background worker, which
runs the LangGraph workflow. The agents read data through a file cache (to avoid repeated downloads), compute
their results in Python, ask Ollama for explanations, and store every result in MongoDB. The final report is
assembled from the stored results.

### 3.2 Agents

| Agent | Computes (Python) | LLM writes |
|---|---|---|
| 1. Market research | Moving averages (20, 50, 200 days), EMA, RSI, MACD, Bollinger bands, trend rule, volume, return against the NIFTY 50 over the same days | A short explanation of the readings |
| 2. Financial news | Collection, de-duplication and relevance capping of recent headlines | Per article: summary, sentiment, category, relevance; a digest |
| 3. Stock analysis | Growth, margins, ROE, ROA, debt to equity, current ratio, EPS, P/E, P/B from the annual statements; rule based assessments; bank-specific handling | An explanation of the ratios |
| 4. Risk assessment | Volatility, beta, correlation, maximum drawdown with dates, Sharpe ratio, return distribution, diversification | An explanation of the historical risk |
| 5. Portfolio optimisation | Weights by the chosen method, whole shares for the amount, expected figures, walk-forward backtest against equal weights and the NIFTY 50 | An explanation of the allocation |

The supervisor validates the request, routes the workflow, retries only temporary data-source failures within a
time budget, checks the outputs, and builds the report: sections per stock, key observations, sources, data
limitations, a glossary and a trace of every number to the agent output it came from.

### 3.3 Keeping the language model honest

The central design rule is that the model never produces a figure. It receives a small JSON document of computed
facts, including rule based *readings* (for example "MACD is below its signal line (momentum weakening)"), and is
asked to restate them. Each answer goes through these checks:

1. it must match the JSON schema, with no extra fields;
2. every number in it must appear in the facts, allowing for rounding;
3. it must not contradict a reading (pairs such as *above* / *below its 200-day average*, *outperformed* /
   *underperformed*);
4. a stated gap to the NIFTY 50 must equal the computed difference;
5. in the report's key observations, each sentence about one stock must use only that stock's readings and
   figures, and every stock must be mentioned.

A failed answer is retried once with the reason, then sent to the fallback model, and finally replaced by a rule
based template. The report records which model wrote each text, or that a template was used. If Ollama is not
running at all, every agent still finishes with templates.

### 3.4 Data model

Nine MongoDB collections with strict `$jsonSchema` validators and indexes: `users`, `user_avatars`, `stocks`,
`market_data`, `financial_news`, `agent_results` (the source of truth for agent outputs), `risk_reports` and
`portfolios` (write-once projections), and `analysis_reports` (the job, its status history and the final report).
A storage guard blocks large writes before the 512 MB free tier is full. Details:
[database_design.md](database_design.md).

### 3.5 Memory strategy

One model is loaded at a time and unloaded after a workflow. The client picks the 1.7B model only when enough RAM
is free (`LLM_MIN_FREE_RAM_MB`, set to 3,000 MB after the Phase 13 measurements, counting RAM the loaded model
already holds) and otherwise the 0.6B model. Agents run one after another by default, prices are fetched once per
analysis and shared, and heavy libraries are imported only when needed.

---

## 4. Implementation

| Part | Main contents |
|---|---|
| Data layer (`backend/app/data`) | Symbol normalisation for NSE and BSE, OHLCV validation (bad rows removed, never filled), file cache with freshness windows, news collection with relevance rules, statement parsing |
| Analysis (`backend/app/analysis`) | Indicators, fundamentals, risk metrics, optimisation (seven methods including an in-house hierarchical risk parity), backtesting without look-ahead |
| LLM (`backend/app/llm`) | One shared Ollama client with model selection, retries and fallbacks; prompt templates; output guards |
| Orchestration (`backend/app/orchestration`) | LangGraph graph, supervisor (validation, routing, retries, output validation), sequential and parallel modes |
| Services and API (`backend/app/services`, `backend/app/api`) | Background runner with recovery after a restart, report builder, PDF export, authentication, rate limits, 33 REST operations |
| Web app (`frontend/src`) | Public landing page; signed-in pages: Overview, Market intelligence, Stock analysis, Financial news, AI agents, Risk analysis, Portfolio optimisation, Reports (with comparison and PDF), Watchlist, Settings, Help; dark and light themes |

**Security.** Passwords are hashed with Argon2id; tokens are short-lived JWTs held in session storage (no cookies,
so no cross-site request forgery); other users' resources answer 404 so ids cannot be probed; rate limits apply
per user; news text is treated as untrusted input in prompts; links are re-validated before they are returned;
profile pictures are re-encoded with their metadata removed; secrets exist only in the local `.env` file.

**Development process.** The work was done in 16 phases (0 to 14, with a separate redesign phase 12B), each on
its own branch, reviewed and approved before it was merged into `main`.

---

## 5. Testing and validation

The full results are in [testing_report.md](testing_report.md).

* **545 automated tests**, 94% statement coverage. They cover calculations, data collection, each agent on its
  own (normal runs, invalid input, missing data, data-source failures, the LLM missing or failing in the middle of
  a run), the workflow, the API, authentication, the database (against a separate test database) and a contract
  test that every call the web app makes exists in the API.
* **Financial validation.** Every metric was recomputed by independent reference code (plain loops, NumPy and
  SciPy, without the libraries the production code uses) on two years of real prices for four NSE stocks and the
  NIFTY 50 and on three companies' annual statements. All 42 comparisons agree to the displayed precision,
  including the Ledoit-Wolf covariance written from the paper and the optimised weights compared with a separate
  solver.
* **Problems found and fixed** during testing included: backtest returns that left out the first purchase cost
  (−17.34% reported for an actual −17.42%), ratios that depended on the order of statement periods, server errors
  without a request id, a model switch in the middle of every run, and AI text that stated the stock's own return
  as its gap to the NIFTY 50.

---

## 6. Results

Measured on the development laptop on 25 November 2026 (12 logical CPUs, 7.68 GB usable RAM, VS Code open).

| Measure | Result |
|---|---|
| One stock, full analysis | 59 s |
| Five stocks with an illustrative portfolio | 249 s (298 s through the API and web app) |
| Share of time spent in the LLM | Most of it; the calculations take well under a second per stock |
| LLM speed | 1.7B: 15 to 16 tokens/s; 0.6B: 31 to 35 tokens/s |
| AI answers accepted after the prompt fixes | 18 of 18 in the benchmark (11 of 18 before) |
| Memory: backend / Ollama with 0.6B / with 1.7B / browser | 0.2 GB / 0.9 to 1.1 GB / 1.5 to 1.75 GB / 0.5 GB |
| MongoDB response times | 4 to 22 ms median |
| A stored two-stock run (RELIANCE and TCS, 23 Nov 2026) | 72 s, 125 of 125 numbers in the report traced to an agent |

The system's own processes fit within the 3.5 GB budget set at the start. The whole machine, however, reached
7.5 GB in use during runs, above the 6.5 GB target, because Windows and the other open programs already used about
6 GB. This is why the 1.7B model is now used only when 3 GB is free.

---

## 7. Discussion and limitations

* **Data quality.** yfinance is an unofficial interface to Yahoo Finance. Data can be delayed, revised or missing,
  and the interface can break when Yahoo changes. Statements are annual, so they lag the latest quarter.
* **News coverage.** RSS feeds give a partial picture, and a 0.6B model judges sentiment less reliably than a larger
  one. Python caps the model's relevance labels, and articles without a model answer are marked *uncertain* rather
  than guessed.
* **Model quality.** Small models write plainer and sometimes clumsy text. The checks keep the facts right, but they
  cannot make the wording good; the rule based readings are always shown beside the AI text.
* **Backtests.** The stocks are chosen today, so any backtest has hindsight (selection bias). One current
  risk-free rate is used for the whole period, and taxes, slippage and lot sizes are ignored. Every backtest states
  these limits.
* **Validation scope.** The financial validation shows that the code computes what the formulas define. It cannot
  show that the source data is correct.
* **Hardware.** On an 8 GB laptop the comfortable configuration is the 0.6B model with other programs closed; the
  1.7B model needs free memory that a typical developer setup does not always have.
* **Not advice.** NeuralVest is not registered with SEBI and gives no recommendations. It shows what happened in the
  past.

---

## 8. Conclusion

NeuralVest shows that a useful, multi-agent financial analysis system can run on an ordinary laptop without paid
services, provided the language model is kept to the task it can do reliably. Moving every calculation into tested
code and treating the model as a writer whose text must pass explicit checks made a 0.6B model usable: its answers
are either consistent with the computed facts or replaced. The testing phase showed the value of this approach
twice over: validation against independent references found real calculation errors, and the guards found the
exact mistakes the small models make, which then led to better prompts rather than looser checks.

---

## 9. Future work

* Quarterly results and corporate actions from official exchange filings, where their terms allow it.
* A larger or better-quantised model when more memory is available, chosen per task.
* Historical risk-free rates for backtests instead of one current rate.
* Frontend unit tests (for example with Vitest) alongside the existing contract test.
* Alerts for watchlist stocks when a reading changes.
* Optional packaging (for example Docker) for machines with more memory.

---

## References

1. LangGraph documentation, LangChain Inc. https://langchain-ai.github.io/langgraph/
2. Ollama documentation. https://github.com/ollama/ollama/tree/main/docs
3. Qwen3 model family, Alibaba Cloud (Apache 2.0). https://huggingface.co/Qwen
4. yfinance, R. Aroussi (Apache 2.0). https://github.com/ranaroussi/yfinance
5. PyPortfolioOpt, R. A. Martin, *Journal of Open Source Software* 6(61), 3066 (2021).
6. O. Ledoit and M. Wolf, "A well-conditioned estimator for large-dimensional covariance matrices", *Journal of
   Multivariate Analysis* 88(2), 365–411 (2004).
7. M. López de Prado, "Building diversified portfolios that outperform out of sample", *Journal of Portfolio
   Management* 42(4), 59–69 (2016) (hierarchical risk parity).
8. J. W. Wilder, *New Concepts in Technical Trading Systems* (1978) (RSI).
9. W. F. Sharpe, "The Sharpe ratio", *Journal of Portfolio Management* 21(1), 49–58 (1994).
10. Reserve Bank of India, Treasury bill auction results. https://www.rbi.org.in
11. FastAPI documentation. https://fastapi.tiangolo.com
12. MongoDB Atlas documentation. https://www.mongodb.com/docs/atlas/
