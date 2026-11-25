# NeuralVest: Presentation Outline

Twelve slides for a 12 to 15 minute talk, plus a short live demo. Each slide lists what to show and what to
say. Figures come from [testing_report.md](testing_report.md) and [project_report.md](project_report.md);
diagrams from [diagrams.md](diagrams.md); screenshots from `docs/screenshots/`.

---

### Slide 1. Title

**Show:** NeuralVest logo and name · "Multi-agent financial intelligence for Indian stocks, on an 8 GB laptop" ·
your name · November 2026 · "Educational project, not investment advice".

**Say:** One sentence on what it is: five AI agents analyse NSE and BSE stocks and write one report you can check,
all on a normal laptop with free tools.

---

### Slide 2. The problem

**Show:** Three short points.
* Prices, news and annual statements are public but scattered.
* Combining them needs time and financial knowledge.
* Language models summarise well but state wrong numbers confidently.

**Say:** In finance a confident wrong number is worse than no answer. That shaped every design decision.

---

### Slide 3. Aim and constraints

**Show:** Left: the aim, a report where every number is computed by code and the AI only explains.
Right: constraints as icons: CPU only · 8 GB RAM · zero budget · GitHub only, no hosting · no scraping of exchange
websites.

**Say:** The constraints are real: this is the laptop it was built and measured on.

---

### Slide 4. Architecture

**Show:** The system architecture diagram (diagrams.md §1).

**Say:** Walk left to right: browser, FastAPI, a background runner, the LangGraph supervisor with five agents,
Python calculations, Ollama for text, MongoDB Atlas for storage, and the free data sources.

---

### Slide 5. The five agents

**Show:** The agent workflow diagram (diagrams.md §2) and a five-row table: agent · what Python computes · what the
AI writes.

**Say:** Market research, news, fundamentals, risk and portfolio. Sequential by default to save memory; the
supervisor skips what cannot run and retries only temporary failures.

---

### Slide 6. Keeping the AI honest (key slide)

**Show:** The answer-acceptance flow (diagrams.md §2, "How an AI answer is accepted"), and one real example:
* the model wrote: "TCS underperformed the NIFTY 50 by 18.31%";
* the computed truth: −18.31% is TCS's own return; the gap is 16.33 points;
* result: rejected, retried with the reason, corrected.

**Say:** The model never produces a figure. Every answer is checked for invented numbers, contradictions, the
benchmark gap and facts attached to the wrong stock. If it still fails, a rule based text is used and labelled.

---

### Slide 7. Live demo (3 to 4 minutes)

**Show:** The app, signed in.
1. Overview: market overview and watchlist.
2. Stock analysis: start RELIANCE and TCS with ₹1,00,000, moderate risk. While it runs, open **AI agents** to show
   each agent's progress.
3. The report: key readings beside the AI explanation, the agent shown under each figure ("↳ Risk assessment"), the traceability line ("all N numbers traced"), the portfolio and backtest. (The landing page's "trace any number" section lets you click figures.)
4. Download the PDF.

**Fallback:** if time or memory is short, open a saved report from **Reports** instead of starting a new run (an
analysis of two stocks takes about one to two minutes).

---

### Slide 8. Testing and validation

**Show:** Three numbers: **545 tests** · **94% coverage** · **42 of 42 metrics** match independent references on
real data. Under them, the bugs found by the validation: backtest return −17.34% shown for an actual −17.42%;
ratios depending on data order; a model swap in the middle of every run.

**Say:** The validation recomputes every metric with separate code that uses none of the production libraries. It
found real errors, which is the point of doing it.

---

### Slide 9. Performance on 8 GB

**Show:** A small table:

| | Result |
|---|---|
| One stock | 59 s |
| Five stocks + portfolio | 249 s |
| AI speed, 1.7B / 0.6B | 15–16 / 31–35 tokens per second |
| Memory: backend / AI model / browser | 0.2 / 0.9–1.7 / 0.5 GB |
| Database queries | 4–22 ms |

**Say:** Most of the time is the language model; the calculations take under a second per stock. NeuralVest's own
processes fit the budget, but with other programs open the laptop is near its limit, so the larger model is used
only when 3 GB is free.

---

### Slide 10. Better prompts, not looser checks

**Show:** Before and after: 11 of 18 AI answers accepted, then 18 of 18; the 1.7B market explanation from 13–21 s
to 7 s.

**Say:** The checks showed the models copy a pattern ("outperformed by" plus a number). Writing the reading as
"outperformed the NIFTY 50 by 6.1 percentage points" fixed it. The checks stayed as strict as before.

---

### Slide 11. Limitations

**Show:** Five short points: unofficial Yahoo Finance data · partial news coverage · small models write plain text ·
backtests have hindsight · not investment advice (not SEBI registered).

**Say:** Be direct about these. They are stated in the app and in every report too.

---

### Slide 12. Conclusion and future work

**Show:** One sentence: "Keep the model to what it does reliably, and check everything it writes." Future work:
quarterly filings, historical risk-free rates, frontend unit tests, watchlist alerts, a larger model when memory
allows. The GitHub link and the MIT license.

**Say:** Thank the audience; invite questions.

---

## Likely questions

| Question | Short answer |
|---|---|
| Why not a larger model or an API like GPT? | Zero budget and a CPU-only 8 GB laptop. The design makes a small local model sufficient because it never computes figures. |
| How do you know the numbers are right? | 42 metrics recomputed by independent code on real data, plus 545 tests; every number in a report is traced to the agent that computed it. |
| What if Ollama is not running? | Every agent finishes with rule based text, labelled as such; the figures are unaffected. |
| Is the data real time? | No: end of day data from Yahoo Finance, which can be delayed. Each report shows its data date. |
| Why LangGraph? | A predictable, testable state graph with a supervisor, instead of agents choosing their own route. |
| Could someone use this to invest? | It is educational and not registered advice; it describes the past only. |
