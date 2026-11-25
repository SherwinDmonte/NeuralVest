# NeuralVest Diagrams

Four diagrams in Mermaid, which GitHub draws directly. They follow the code: the workflow diagram is based on
the graph LangGraph compiles (`app/orchestration/graph.py`), and the database diagram on the document models
(`app/database/models.py`) and indexes (`app/database/indexes.py`).

1. [System architecture](#1-system-architecture) (task 14.1.2)
2. [Agent workflow (LangGraph)](#2-agent-workflow-langgraph) (task 14.1.3)
3. [Data flow of one analysis](#3-data-flow-of-one-analysis)
4. [Database schema](#4-database-schema) (task 14.1.4)

---

## 1. System architecture

Everything runs on one Windows laptop except MongoDB Atlas and the public data sources.

```mermaid
flowchart LR
    subgraph Browser
        UI["React app<br/>Vite · Tailwind · Recharts"]
    end

    subgraph Laptop["Windows laptop (CPU only, 8 GB RAM)"]
        API["FastAPI<br/>auth · rate limits · error envelope"]
        Runner["Analysis runner<br/>one worker, job queue, recovery"]
        Graph["LangGraph supervisor<br/>5 agents + validation + report"]
        Calc["Python calculations<br/>pandas · NumPy · SciPy · PyPortfolioOpt"]
        LLM["Ollama<br/>qwen3:1.7b / qwen3:0.6b"]
        Cache[("File cache<br/>data/cache")]
    end

    subgraph Cloud["Free external services"]
        Atlas[("MongoDB Atlas M0")]
        Yahoo["Yahoo Finance<br/>(yfinance)"]
        News["RSS feeds · GDELT"]
    end

    UI -- "REST + JWT" --> API
    API --> Runner --> Graph
    API --> Atlas
    Graph --> Calc
    Graph -- "explanations only" --> LLM
    Graph --> Atlas
    Calc --> Cache
    Cache -. "on a miss" .-> Yahoo
    Graph --> News
```

| Part | Responsibility |
|---|---|
| React app | Pages, charts and report view; keeps the access token in session storage |
| FastAPI | Validation, authentication, ownership checks, rate limits, one error format |
| Analysis runner | Runs one analysis at a time in a background thread; queued jobs survive a restart |
| LangGraph supervisor | Validates input, runs the agents, retries temporary failures, checks the AI text, builds the report |
| Python calculations | Every number in a report (indicators, ratios, risk, optimisation, backtest) |
| Ollama | Plain-language explanations of numbers it is given; never computes or invents figures |
| MongoDB Atlas | Users, prices, news, agent results, portfolios, reports |

---

## 2. Agent workflow (LangGraph)

The default is **sequential** (`AGENT_EXECUTION_MODE=sequential`), which keeps memory low on 8 GB. Dashed
arrows are decisions the supervisor makes from the state.

```mermaid
flowchart TD
    start([Request: 1 to 10 symbols,<br/>optional amount and risk preference]) --> V[validate_input]
    V -- "no valid symbol" --> R
    V -- "valid symbols" --> M["market_research<br/>Agent 1: prices, indicators, NIFTY 50 comparison"]
    M -- "no stock has prices" --> R
    M --> N["financial_news<br/>Agent 2: headlines, sentiment, digest"]
    N --> S["stock_analysis<br/>Agent 3: annual statements, ratios"]
    S --> K["risk_assessment<br/>Agent 4: volatility, beta, drawdown, Sharpe"]
    K --> O[output_validation<br/>sanitise numbers, check AI text]
    O -- "amount given and 2+ stocks with data" --> P["portfolio_optimization<br/>Agent 5: weights, whole shares, backtest"]
    O -- "otherwise" --> R
    P --> R[report<br/>sections, key observations, number tracing]
    R --> done([Report saved to MongoDB])
```

**Parallel mode** (`AGENT_EXECUTION_MODE=parallel`): after market research, news, stock analysis and risk
assessment run at the same time, and output validation waits for all three. It is faster but needs more
memory, so it is off by default.

```mermaid
flowchart LR
    M[market_research] --> N[financial_news] & S[stock_analysis] & K[risk_assessment]
    N & S & K --> O[output_validation]
```

### How an AI answer is accepted

Each agent computes its figures first. Only then does it ask the model to explain them, and the answer
must pass every check.

```mermaid
flowchart LR
    F["Facts computed in Python"] --> Q["Primary model<br/>qwen3:1.7b"]
    Q --> C{"Checks:<br/>valid JSON schema · no invented numbers ·<br/>no contradiction of a reading ·<br/>right gap to the NIFTY 50 ·<br/>facts on the right stock"}
    C -- "pass" --> A["Answer used, model recorded"]
    C -- "fail" --> Q2["Retry with the reason"]
    Q2 --> C2{"Checks"}
    C2 -- "pass" --> A
    C2 -- "fail" --> Fb["Fallback model<br/>qwen3:0.6b (same two tries)"]
    Fb -- "still fails" --> T["Rule based template,<br/>labelled as such"]
    Fb -- "pass" --> A
```

With less free RAM than `LLM_MIN_FREE_RAM_MB` (counting the RAM a loaded primary model already holds), the
client starts at the fallback model.

---

## 3. Data flow of one analysis

```mermaid
sequenceDiagram
    autonumber
    actor U as You (browser)
    participant API as FastAPI
    participant RUN as Runner
    participant G as LangGraph agents
    participant Y as Yahoo / news feeds
    participant O as Ollama
    participant DB as MongoDB Atlas

    U->>API: POST /api/analysis/start (JWT)
    API->>DB: analysis_reports: status queued
    API-->>U: 202 request_id
    RUN->>G: run the workflow
    loop each agent, each stock
        G->>Y: prices, statements, headlines (file cache first)
        G->>G: compute every figure in Python
        G->>O: explain the computed facts
        O-->>G: text, checked by the guards
        G->>DB: agent_results (+ market_data, financial_news)
    end
    G->>DB: portfolios, risk_reports (projections)
    G->>DB: analysis_reports: final report, status completed or partial
    loop every 2 to 3 s
        U->>API: GET /status
        API-->>U: progress per agent
    end
    U->>API: GET /api/reports/{report_id} or /pdf
    API->>DB: read
    API-->>U: report (PDF generated on request)
```

---

## 4. Database schema

`agent_results` is the source of truth for everything an agent computed. `portfolios` and `risk_reports` are
write-once projections that point back to it. `analysis_reports` holds the job and the final report.

```mermaid
erDiagram
    users ||--o| user_avatars : "has (optional)"
    users ||--o{ analysis_reports : "owns"
    users ||--o{ portfolios : "owns"
    analysis_reports ||--|{ agent_results : "request_id"
    analysis_reports ||--o| portfolios : "request_id"
    analysis_reports ||--o| risk_reports : "request_id"
    agent_results }o--o{ portfolios : "source_agent_result_ids"
    agent_results }o--o{ risk_reports : "source_agent_result_ids"
    stocks ||--o{ market_data : "symbol"
    stocks ||--o{ financial_news : "symbol"

    users {
        string user_id UK
        string email UK
        string name
        string password_hash "Argon2id"
        array watchlist "up to 20 symbols"
        date avatar_updated_at
        date created_at
    }
    user_avatars {
        string user_id UK
        string content_type "image/webp"
        binary data "256 x 256, max 256 KB"
        int size_bytes
        date updated_at
    }
    stocks {
        string symbol UK
        string company_name "text index"
        string exchange "NSE or BSE"
        string sector
        string industry
    }
    market_data {
        string symbol "unique with date"
        date date
        double open
        double high
        double low
        double close
        double adjusted_close
        long volume
        string source
    }
    financial_news {
        string symbol "unique with url_hash"
        string url_hash
        string headline
        string article_url
        date publication_date
        string sentiment
        string category
        string relevance
    }
    agent_results {
        string request_id "unique with agent_name, scope_key"
        string agent_name
        string scope_key "symbol or __request__"
        string execution_status
        object output
        string llm_model
        double execution_time
    }
    analysis_reports {
        string report_id UK
        string request_id UK
        string user_id
        array symbols
        string status "queued to completed"
        array status_history
        object final_summary "the report"
        date requested_at
    }
    portfolios {
        string portfolio_id UK
        string request_id UK
        string user_id
        array stock_allocations
        double investment_amount
        string optimization_method
    }
    risk_reports {
        string request_id
        array symbols
        object volatility
        object beta
        object sharpe_ratio
        object maximum_drawdown
        object risk_free_rate
    }
```

Every collection also has a strict `$jsonSchema` validator, and every document a `schema_version`. Field
level details and the reasons behind each index are in [database_design.md](database_design.md).
