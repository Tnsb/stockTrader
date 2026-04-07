# StockTrader: Signals, Strategies, and Disagreement

Two competing LLM-powered strategy agents analyze the same stock data and produce independent recommendations. An evaluator compares their outputs and explains agreement or disagreement. When agents disagree, a **Debate Mode** bonus round lets each agent rebut the other's reasoning.

## Strategies

- **Strategy A: Momentum Trader** -- follows trends, buys strength, sells weakness.
- **Strategy B: Value Contrarian** -- buys overreactions to the downside, sells overreactions to the upside.

## Stack

- **Python 3.10+**
- **yfinance** for market data (no LLM calls)
- **Groq API** (`llama-3.3-70b-versatile`) for strategy and evaluator LLM calls
- **LangGraph** for orchestration (parallel strategy branches, conditional evaluator routing, debate fan-out)

## Repository Structure

```
stockTrader/
  README.md
  requirements.txt
  .env.example
  src/
    main.py              # CLI entrypoint
    graph.py             # LangGraph state, nodes, and routing
    market_data.py       # yfinance fetch + indicator computation (no LLM)
    strategy_agents.py   # Momentum and Contrarian strategy + debate rebuttal
    evaluator.py         # Agreement/disagreement evaluator
    io_utils.py          # JSON writing + summary aggregation
    orchestration.py     # Thin wrapper for graph construction
  prompts/
    strategy_a.txt       # Momentum Trader system prompt
    strategy_b.txt       # Value Contrarian system prompt
    evaluator.txt        # Evaluator system prompt
    debate_rebuttal.txt  # Debate Mode rebuttal prompt
  outputs/               # Pre-generated JSON outputs (grading without API key)
    JNJ.json
    NVDA.json
    PYPL.json
    KO.json
    TSLA.json
    summary.json
    langgraph_workflow.mmd
  report/
    report.md
    report.pdf
    ai_use_appendix.md
    ai_use_appendix.pdf
```

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

## Run

Analyze the default stock set (JNJ, NVDA, PYPL, KO, TSLA):

```bash
python -m src.main
```

Analyze custom tickers:

```bash
python -m src.main --tickers AAPL MSFT META AMZN
```

Deterministic fallback mode (no API key needed):

```bash
python -m src.main --mock-llm
```

## Output

Each run produces:

- `outputs/<TICKER>.json` -- per-stock analysis with market data, both strategy outputs, evaluator analysis, and debate rebuttals (if disagreement)
- `outputs/summary.json` -- aggregated agreement/disagreement counts
- `outputs/langgraph_workflow.mmd` -- LangGraph Mermaid diagram source

## Pre-generated Outputs

Pre-generated outputs from real Groq API calls are included in `outputs/` so grading can be done without rerunning code or requiring an API key.

## Bonus: Debate Mode

When the evaluator detects disagreement, both agents enter a debate round where each sees the other's reasoning and produces a rebuttal. The debate output is saved as a `debate` field in the per-stock JSON. In this run, no agent changed its position during debate, but several increased their confidence scores.
