// Landing page copy and the figures it quotes. Every number here comes from snapshot.json,
// which backend/scripts/make_landing_snapshot.py copies from a real stored analysis.
import snapshot from './snapshot.json'
import { fmtDate, num, shortSymbol } from '../utils/format'

export { snapshot }
export const REPO = 'https://github.com/SherwinDmonte/NeuralVest'
export const CTA = 'Create a free account'
export const TEST_COUNT = 435 // backend tests passing at the time of writing (pytest)

export const LINKS = [
  { href: '#how', label: 'How it works' },
  { href: '#explore', label: 'Explore a report' },
  { href: '#faq', label: 'FAQ' },
]

const [FIRST, SECOND] = snapshot.run.symbols
export const RUN_SYMBOLS = snapshot.run.symbols
export const RUN_DATE = fmtDate(snapshot.run.completed_at)
export const RUN_SECONDS = Math.round((new Date(snapshot.run.completed_at) - new Date(snapshot.run.requested_at)) / 1000)
export const RUN_LABEL = `${RUN_SYMBOLS.map(shortSymbol).join(' and ')}, analysed on ${RUN_DATE}`

const s1 = snapshot.stocks[FIRST]
const signed = (v, d = 2) => (v == null ? 'n/a' : `${v < 0 ? '−' : v > 0 ? '+' : ''}${num(Math.abs(v), d)}`)
export const fmtPct = (v, d = 2) => `${signed(v, d)}%`
export const fmtSigned = signed

const win = s1.window
const winText = `${fmtDate(win.from)} to ${fmtDate(win.to)}, ${win.trading_days} trading days`
const dd = s1.max_drawdown
const de = s1.fundamentals.debt_to_equity

// The numbers a visitor can click in the "trace any number" section.
export const TRACES = [
  {
    id: 'ret', value: fmtPct(s1.return_1y_pct), label: `${shortSymbol(FIRST)} one year return`, agent: 'Market research',
    how: `Close on ${fmtDate(win.to)} against the close on ${fmtDate(win.from)}`, data: `Daily prices from Yahoo Finance · ${winText}`,
  },
  {
    id: 'nifty', value: fmtPct(s1.nifty_return_pct), label: 'NIFTY 50 over the same days', agent: 'Market research',
    how: 'The same calculation on the NIFTY 50 index (^NSEI), the benchmark for every comparison', data: `Yahoo Finance · ${winText}`,
  },
  {
    id: 'vol', value: `${num(s1.volatility_pct)}%`, label: 'Annualised volatility', agent: 'Risk assessment',
    how: 'Standard deviation of daily returns × √252', data: `${s1.risk_window.observations} daily returns · ${winText}`,
  },
  {
    id: 'beta', value: num(s1.beta), label: 'Beta against the NIFTY 50', agent: 'Risk assessment',
    how: 'Covariance of daily returns with the NIFTY 50 ÷ variance of the NIFTY 50', data: `${s1.beta_observations} paired daily returns`,
  },
  {
    id: 'dd', value: fmtPct(dd.pct), label: 'Largest fall from a peak', agent: 'Risk assessment',
    how: `From the peak on ${fmtDate(dd.peak)} to the low on ${fmtDate(dd.trough)}${dd.recovered ? '' : ', not yet recovered'}`, data: 'Daily closes in the same window',
  },
  ...(de ? [{
    id: 'de', value: num(de.value), label: 'Debt to equity', agent: 'Stock analysis',
    how: de.formula.charAt(0).toUpperCase() + de.formula.slice(1), data: `Annual balance sheet · ${de.period}`,
  }] : []),
]
export const traceById = Object.fromEntries(TRACES.map((t) => [t.id, t]))

const sec = (k) => snapshot.run.agent_seconds[k]
export const STORY = [
  { key: 'input', title: 'You pick the stocks', agent: null,
    text: 'Type NSE symbols like RELIANCE or BSE codes like 500325. Add an amount and a risk preference if you want an illustrative portfolio.' },
  { key: 'market_research', title: 'Market research', agent: 'Agent 1',
    text: 'Daily prices, moving averages, RSI, MACD and a comparison with the NIFTY 50 over the same days.', seconds: sec('market_research') },
  { key: 'financial_news', title: 'Financial news', agent: 'Agent 2',
    text: 'Recent headlines from Indian business feeds, each with a sentiment label and a link to the source.', seconds: sec('financial_news') },
  { key: 'stock_analysis', title: 'Stock analysis', agent: 'Agent 3',
    text: 'Ratios from the annual statements: growth, margins, return on equity and debt, each with its formula and year.', seconds: sec('stock_analysis') },
  { key: 'risk_assessment', title: 'Risk assessment', agent: 'Agent 4',
    text: 'Volatility, beta, the largest fall from a peak and the Sharpe ratio against the RBI 91 day T bill rate.', seconds: sec('risk_assessment') },
  { key: 'portfolio_optimization', title: 'Portfolio optimization', agent: 'Agent 5',
    text: 'Weights in whole shares for two or more stocks, tested on past prices against equal weights and the NIFTY 50.', seconds: sec('portfolio_optimization') },
  { key: 'report', title: 'A report you can check', agent: 'Supervisor',
    text: `Every number in the text is matched to the agent that computed it: ${snapshot.run.numbers_traced} of ${snapshot.run.numbers_traced} in the ${RUN_DATE} run.`, seconds: sec('report') },
]

export const SOURCES = [
  ['Yahoo Finance', 'daily prices, annual statements'],
  ['NIFTY 50 (^NSEI)', 'benchmark for every comparison'],
  ['Reserve Bank of India', `91 day T bill, ${num(snapshot.risk_free_rate.value_pct)}%`],
  ['Indian business news feeds', 'headlines from the last 14 days'],
  ['Qwen3 through Ollama', 'explanations only, on your computer'],
]

export const FAQ = [
  ['Is NeuralVest investment advice?', 'No. It is an educational project and not a SEBI registered adviser. Reports describe what happened in the past and suggest nothing about what you should buy or sell.'],
  ['Is the market data real time?', 'No. Prices are end of day data from Yahoo Finance through the yfinance library and can be delayed. Every report shows the date its data is from.'],
  ['Which stocks can I analyse?', 'Any NSE symbol or BSE code that Yahoo Finance covers, up to 10 in one analysis. The NIFTY 50 is the benchmark for every comparison.'],
  ['How accurate is the AI text?', 'The numbers are always computed in Python. The local model only explains them, and its text is rejected when it uses a number that is not in the data or contradicts a computed reading. Its wording can still be clumsy, so the rule based readings are shown beside it.'],
  ['Does my data leave my computer?', 'The AI model runs on your machine. Prices and news are downloaded from public sources, and your account and reports are stored in your own MongoDB Atlas database.'],
  ['What do I need to run it?', 'Python 3.12, Node, Ollama with a Qwen3 model and a free MongoDB Atlas cluster. It was built and measured on an 8 GB Windows laptop without a graphics card.'],
  ['How long does an analysis take?', `About 30 to 60 seconds for one stock and one to two minutes for two on a laptop CPU. The ${RUN_DATE} run of two stocks took ${RUN_SECONDS} seconds.`],
  ['What does it cost?', 'Nothing. Every tool it uses is free, and the code is open source on GitHub.'],
]

export { FIRST, SECOND }
