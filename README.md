# NeuralVest — AI-Powered Financial Intelligence Platform

> **Status:** early development (Phase 1: environment setup). See [tasks.md](tasks.md) for progress.

NeuralVest is an educational, multi-agent financial intelligence system for Indian equities (NSE/BSE). Five specialized agents (Market Research, Financial News, Stock Analysis, Risk Assessment and Portfolio Optimization) are coordinated by a LangGraph supervisor. They use a local Qwen3 model through Ollama, store results in MongoDB Atlas and present them in a React dashboard. Everything runs on a CPU-only, 8 GB RAM Windows laptop using free tools.

> **Disclaimer:** NeuralVest is an educational project. Its outputs are illustrative, are not investment advice and are not real-time market data.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, Vite, Tailwind CSS, Recharts, Axios, React Router, Lucide React |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Agents | LangGraph, Ollama, Qwen3 (1.7B / 0.6B) |
| Data & analysis | yfinance, pandas, NumPy, SciPy, PyPortfolioOpt, feedparser, BeautifulSoup, pypdf |
| Database | MongoDB Atlas (free tier), PyMongo |

## Documentation

- [Architecture](docs/architecture.md)
- [Database design](docs/database_design.md)
- [Windows setup guide](docs/setup_guide.md)

## Quick start (development)

See [docs/setup_guide.md](docs/setup_guide.md) for full instructions.

```powershell
# Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd ..\frontend
npm install
npm run dev
```

*Sections to be completed in later phases: features, screenshots, usage, testing, license.*
