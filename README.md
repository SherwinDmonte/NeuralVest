<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="NeuralVest: five AI agents analyse NSE and BSE stocks; every number is computed and traced" src="docs/assets/banner-light.svg" width="100%">
</picture>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.165-009688?logo=fastapi&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.2-1C3C3C">
  <img alt="Qwen3 on Ollama" src="https://img.shields.io/badge/Qwen3-Ollama%20(local)-000000?logo=ollama&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="MongoDB Atlas" src="https://img.shields.io/badge/MongoDB-Atlas%20free%20tier-47A248?logo=mongodb&logoColor=white">
  <br>
  <img alt="545 tests passing" src="https://img.shields.io/badge/tests-545%20passing-2EA44F">
  <img alt="94% coverage" src="https://img.shields.io/badge/coverage-94%25-2EA44F">
  <img alt="Runs on 8 GB RAM, CPU only" src="https://img.shields.io/badge/runs%20on-8%20GB%20RAM%2C%20CPU%20only-438BFF">
  <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-9B6BFF">
</p>

<p align="center">
  <a href="#what-it-does">What it does</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#api">API</a> ·
  <a href="#testing-and-performance">Testing</a> ·
  <a href="#documentation">Docs</a>
</p>

**NeuralVest** analyses stocks listed on the NSE and BSE. Five specialised agents (market research, financial news,
stock analysis, risk assessment and portfolio optimisation) are coordinated by a LangGraph supervisor and write one
report per request. Every figure is computed in Python from public end-of-day data. A small local language model
(Qwen3 through Ollama) only **explains** figures it is given, and every explanation is checked before you see it.

It runs entirely on a Windows laptop with **8 GB of RAM and no graphics card**, using free tools and the MongoDB Atlas
free tier.

> [!IMPORTANT]
> NeuralVest is an educational project. It is not registered with SEBI, its reports describe the past, and nothing
> in them is investment advice. Prices are end-of-day data from Yahoo Finance and can be delayed.

---

## What it does

| | |
|---|---|
| **Five agents, one report** | Market research (indicators, trend, comparison with the NIFTY 50), financial news (sentiment per article and a digest), stock analysis (ratios from the annual statements), risk assessment (volatility, beta, drawdown, Sharpe, correlation) and portfolio optimisation (weights, whole shares, backtest). |
| **Numbers you can check** | Every figure is computed by tested Python code, shown with its formula and data window, and traced to the agent that produced it. A report says how many of its numbers were traced (for example 125 of 125). |
| **An AI that is not allowed to guess** | The model receives computed facts and restates them. Answers with invented numbers, contradictions of a computed reading, a wrong gap to the NIFTY 50, or a fact on the wrong stock are rejected, retried, and if necessary replaced by rule based text, labelled as such. |
| **Illustrative portfolios** | Seven methods (max Sharpe, min volatility, efficient risk or return, equal weight, inverse volatility, hierarchical risk parity), risk preferences with weight limits, whole-share allocation for your amount, and a walk-forward backtest with costs against equal weights and the NIFTY 50. |
| **A full web app** | Accounts, market overview of NIFTY 50, SENSEX and 30 curated stocks, watchlist, live agent progress, saved reports with comparison and PDF export, dark and light themes, `Ctrl K` search. |
| **Built for small machines** | One model in memory at a time, the larger model only when RAM allows, agents in sequence by default, cached data, and a storage guard for the 512 MB database tier. |

---

## Screenshots

<!-- Screenshots go in docs/screenshots/<name>-dark.png and <name>-light.png. -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/landing-dark.png">
  <img alt="NeuralVest landing page" src="docs/screenshots/landing-light.png" width="100%">
</picture>

<p align="center"><sub>The landing page, in the theme that matches your GitHub setting. Every module below shows both themes.</sub></p>

<details open>
<summary><b>Overview</b>: market overview, watchlist and your latest activity</summary>

| Dark | Light |
|---|---|
| <img alt="Overview, dark theme" src="docs/screenshots/overview-dark.png"> | <img alt="Overview, light theme" src="docs/screenshots/overview-light.png"> |
</details>

<details>
<summary><b>Stock analysis</b>: the report of the five agents</summary>

| Dark | Light |
|---|---|
| <img alt="Stock analysis, dark theme" src="docs/screenshots/analysis-dark.png"> | <img alt="Stock analysis, light theme" src="docs/screenshots/analysis-light.png"> |
</details>

<details>
<summary><b>AI agents</b>: the agent network and each step of a run</summary>

| Dark | Light |
|---|---|
| <img alt="AI agents, dark theme" src="docs/screenshots/agents-dark.png"> | <img alt="AI agents, light theme" src="docs/screenshots/agents-light.png"> |
</details>

<details>
<summary><b>Market intelligence</b>: NIFTY 50, SENSEX and the 30 curated stocks</summary>

| Dark | Light |
|---|---|
| <img alt="Market intelligence, dark theme" src="docs/screenshots/market-dark.png"> | <img alt="Market intelligence, light theme" src="docs/screenshots/market-light.png"> |
</details>

<details>
<summary><b>Financial news</b>: stored articles with AI sentiment</summary>

| Dark | Light |
|---|---|
| <img alt="Financial news, dark theme" src="docs/screenshots/news-dark.png"> | <img alt="Financial news, light theme" src="docs/screenshots/news-light.png"> |
</details>

<details>
<summary><b>Risk analysis</b>: volatility, drawdown, beta, Sharpe and correlation</summary>

| Dark | Light |
|---|---|
| <img alt="Risk analysis, dark theme" src="docs/screenshots/risk-dark.png"> | <img alt="Risk analysis, light theme" src="docs/screenshots/risk-light.png"> |
</details>

<details>
<summary><b>Portfolio optimisation</b>: allocation, whole shares and a backtest</summary>

| Dark | Light |
|---|---|
| <img alt="Portfolio optimisation, dark theme" src="docs/screenshots/portfolio-dark.png"> | <img alt="Portfolio optimisation, light theme" src="docs/screenshots/portfolio-light.png"> |
</details>

<details>
<summary><b>Reports</b>: saved reports, comparison and PDF</summary>

| Dark | Light |
|---|---|
| <img alt="Reports, dark theme" src="docs/screenshots/reports-dark.png"> | <img alt="Reports, light theme" src="docs/screenshots/reports-light.png"> |
</details>

<details>
<summary><b>Settings</b>: theme, layout, profile picture and system status</summary>

| Dark | Light |
|---|---|
| <img alt="Settings, dark theme" src="docs/screenshots/settings-dark.png"> | <img alt="Settings, light theme" src="docs/screenshots/settings-light.png"> |
</details>

---

## How it works

```mermaid
flowchart LR
    U([Your request:<br/>stocks, amount, risk]) --> V[Validate]
    V --> M["1 · Market research"]
    M --> N["2 · Financial news"]
    N --> S["3 · Stock analysis"]
    S --> K["4 · Risk assessment"]
    K --> O{Check every<br/>AI answer}
    O -- "2+ stocks and an amount" --> P["5 · Portfolio"]
    O --> R[Report: sections,<br/>key observations,<br/>number tracing]
    P --> R
```

Each agent computes its figures first, then asks the model to explain them. An answer must pass every check:

1. valid JSON for its schema, with no extra fields;
2. every number in it appears in the computed facts (allowing for rounding);
3. it does not contradict a rule based reading, such as *above* or *below its 200-day average*;
4. a stated gap to the NIFTY 50 equals the computed difference;
5. in the key observations, each stock's sentences use only that stock's facts, and every stock is mentioned.

A failed answer is retried with the reason, then given to the smaller model, and finally replaced by a template. The
report records which model wrote each text. If Ollama is not running at all, the analysis still completes.

<details>
<summary><b>System architecture</b></summary>

```mermaid
flowchart LR
    subgraph Browser
        UI["React app"]
    end
    subgraph Laptop["Windows laptop, CPU only, 8 GB"]
        API["FastAPI"] --> Runner["Background runner"] --> Graph["LangGraph supervisor<br/>+ 5 agents"]
        Graph --> Calc["Python calculations"]
        Graph -- "explanations only" --> LLM["Ollama: qwen3:1.7b / 0.6b"]
    end
    subgraph Free["Free services"]
        Atlas[("MongoDB Atlas M0")]
        Data["Yahoo Finance · RSS · GDELT"]
    end
    UI -- "REST + JWT" --> API
    API --> Atlas
    Graph --> Atlas
    Calc --> Data
```

More diagrams (data flow, database schema, parallel mode): [docs/diagrams.md](docs/diagrams.md).
</details>

### Tech stack

| Layer | Tools |
|---|---|
| Agents | LangGraph 1.2 · Ollama · Qwen3 1.7B and 0.6B (thinking off, JSON schema output) |
| Analysis | pandas · NumPy · SciPy · PyPortfolioOpt · cvxpy · indicators implemented in the project |
| Data | yfinance (Yahoo Finance) · feedparser and BeautifulSoup (RSS) · GDELT (optional) · pypdf |
| Backend | Python 3.12 · FastAPI · Pydantic · PyMongo · ReportLab (PDF) · PyJWT and pwdlib (Argon2id) |
| Database | MongoDB Atlas free tier, 9 collections with `$jsonSchema` validators |
| Frontend | React 19 · Vite · Tailwind CSS 4 · Recharts · motion · React Router · Axios · Phosphor Icons · Geist |
| Testing | pytest (545 tests) · pytest-cov · oxlint |

---

## Getting started

**You need:** Windows 10 or 11, Python 3.12, Node.js 22 or newer, Git, Ollama and a free MongoDB Atlas cluster. The
[setup guide](docs/setup_guide.md) covers every step, including Atlas and the risk-free rate.

```powershell
git clone https://github.com/SherwinDmonte/NeuralVest.git NEURALVEST
cd NEURALVEST

# Local models
ollama pull qwen3:1.7b
ollama pull qwen3:0.6b

# Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # then fill in MONGODB_URI, JWT_SECRET and the risk-free rate
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd ..\frontend
npm install
Copy-Item .env.example .env
npm run dev                        # http://localhost:5173
```

<details>
<summary><b>Configuration</b>: the settings you fill in</summary>

| Setting (`backend/.env`) | Purpose |
|---|---|
| `MONGODB_URI` | Your Atlas connection string, with the real password (never committed) |
| `JWT_SECRET` | At least 32 random characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `RISK_FREE_RATE_PCT`, `_DATE`, `_SOURCE` | RBI 91-day Treasury bill yield, with its date and source, for Sharpe ratios |
| `LLM_MIN_FREE_RAM_MB` | Free RAM needed to use the 1.7B model (default 3000); otherwise the 0.6B model answers |
| `AGENT_EXECUTION_MODE` | `sequential` (default, lowest memory) or `parallel` |

All settings: [`backend/.env.example`](backend/.env.example) and the [setup guide](docs/setup_guide.md#7-configuration).
</details>

<details>
<summary><b>Using it</b></summary>

1. Open http://localhost:5173 and choose **Create a free account**.
2. In **Stock analysis**, enter one or more symbols: `RELIANCE`, `TCS`, or BSE codes such as `500325`.
3. For two or more stocks, add an amount and a risk preference to get an illustrative portfolio.
4. Follow the agents in **AI agents** while it runs: about a minute for one stock, four minutes for five stocks with
   a portfolio, on an 8 GB laptop.
5. Read the report, compare reports, or download a PDF from **Reports**.

From the terminal instead: `python scripts/run_analysis.py RELIANCE TCS --amount 100000 --no-gdelt` (in `backend`).
</details>

---

## API

FastAPI serves 33 operations under `/api`, with interactive documentation at http://localhost:8000/docs.

| Group | Endpoints |
|---|---|
| Auth | register, login, profile, watchlist, profile picture |
| Analysis | start, status, results, report, rerun |
| Stocks and market | search, price history, indicators, statements, indices, breadth, quotes |
| News, risk, portfolio | stored news and sentiment, risk analysis, optimisation, backtest |
| Reports | list, view, PDF |
| Health | API, database and local model status |

Every error has the same JSON shape with a stable `code` and a request id. Full reference:
[docs/api_documentation.md](docs/api_documentation.md) · schema: [docs/openapi.json](docs/openapi.json).

---

## Testing and performance

| | |
|---|---|
| **Automated tests** | 545 passing, 94% statement coverage: calculations, data sources, each agent alone (including the LLM failing mid-run), the workflow, the API, authentication, the database and a frontend contract test |
| **Financial validation** | Every metric recomputed by independent reference code on two years of real NSE prices and three companies' statements: 42 of 42 agree to the displayed precision |
| **One stock** | 59 s on the development laptop |
| **Five stocks + portfolio** | 249 s |
| **Memory** | Backend 0.2 GB · Ollama 0.9 GB (0.6B) or 1.5 to 1.7 GB (1.7B) · browser 0.5 GB |
| **Database** | 4 to 22 ms median per query (Atlas free tier) |

```powershell
cd backend
python -m pytest
```

Method, all measurements and the problems found and fixed: [docs/testing_report.md](docs/testing_report.md).

---

## Project structure

<details>
<summary>Show the folders</summary>

```text
NEURALVEST/
├── backend/
│   ├── app/
│   │   ├── agents/          the five agents
│   │   ├── analysis/        indicators, fundamentals, risk, optimisation, backtest
│   │   ├── api/             routes, errors, rate limits, authentication dependencies
│   │   ├── data/            prices, statements, news, symbols, validation, cache
│   │   ├── database/        models, validators, indexes, repository
│   │   ├── llm/             Ollama client, prompts, output guards
│   │   ├── orchestration/   LangGraph graph and supervisor
│   │   ├── services/        background runner, report, PDF, auth, profile pictures
│   │   └── main.py          FastAPI app
│   ├── scripts/             run, measure, validate, export and maintenance scripts
│   └── tests/               545 tests
├── frontend/
│   └── src/
│       ├── pages/           the app's pages
│       ├── landing/         the public landing page
│       ├── components/      shared UI and charts
│       └── services/api.js  every API call
└── docs/                    architecture, setup, API, diagrams, testing, report, presentation
```
</details>

---

## Documentation

| Document | Contents |
|---|---|
| [Setup guide](docs/setup_guide.md) | Windows installation, configuration, running, troubleshooting |
| [Architecture](docs/architecture.md) | Design, agent contracts, memory strategy, data limitations, licensing |
| [Diagrams](docs/diagrams.md) | System, agent workflow, data flow and database schema |
| [Database design](docs/database_design.md) | Collections, validators, indexes and storage estimates |
| [API documentation](docs/api_documentation.md) | Endpoints, authentication, errors and rate limits |
| [Testing report](docs/testing_report.md) | Tests, financial validation, performance and memory |
| [Project report](docs/project_report.md) | The final academic report |
| [Presentation outline](docs/presentation_outline.md) | Slides, demo script and likely questions |

---

## Limitations

* Yahoo Finance is reached through the unofficial yfinance library: data can be delayed, revised or missing.
* Annual statements lag the latest quarter; news coverage from RSS feeds is partial.
* Small local models write plain text, and judge news sentiment less reliably than large ones.
* Backtests use stocks chosen today (hindsight) and one current risk-free rate.
* No hosted version: it runs on your own machine.

## License

[MIT](LICENSE) © 2026 Sherwin Dmonte. Third-party packages keep their own licenses (MIT, BSD, Apache 2.0 and, for
the Geist fonts, OFL-1.1); the Qwen3 models are Apache 2.0 and are downloaded by Ollama. Market data belongs to its
providers and is not redistributed in this repository.
