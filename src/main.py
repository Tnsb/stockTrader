from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.graph import build_graph
from src.io_utils import build_summary, write_json


DEFAULT_TICKERS = ["JNJ", "NVDA", "PYPL", "KO", "TSLA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LangGraph StockTrader analysis.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="List of tickers to analyze (default: JNJ NVDA PYPL KO TSLA).",
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory to save per-stock and summary JSON files.",
    )
    parser.add_argument(
        "--prompts-dir",
        default="prompts",
        help="Directory containing strategy and evaluator prompt files.",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use deterministic fallback strategy/evaluator outputs when GROQ_API_KEY is missing.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    if not os.getenv("GROQ_API_KEY") and not args.mock_llm:
        raise EnvironmentError("GROQ_API_KEY is missing. Add it to .env or run with --mock-llm.")

    outputs_dir = Path(args.outputs_dir)
    prompts_dir = Path(args.prompts_dir)

    graph = build_graph(prompts_dir=prompts_dir, outputs_dir=outputs_dir, allow_mock_llm=args.mock_llm)

    all_payloads: List[Dict[str, Any]] = []
    for ticker in args.tickers:
        state = graph.invoke({"ticker": ticker.upper()})
        stock_path = Path(state["output_path"])
        # Rehydrate per-ticker output from generated JSON for a single source of truth.
        payload = json.loads(stock_path.read_text(encoding="utf-8"))
        all_payloads.append(payload)
        print(f"Saved {ticker.upper()} -> {stock_path}")

    summary = build_summary(all_payloads)
    summary_path = outputs_dir / "summary.json"
    write_json(summary_path, summary)
    print(f"Saved summary -> {summary_path}")

    mermaid = graph.get_graph().draw_mermaid()
    diagram_path = outputs_dir / "langgraph_workflow.mmd"
    diagram_path.write_text(mermaid, encoding="utf-8")
    print(f"Saved workflow diagram -> {diagram_path}")


if __name__ == "__main__":
    main()
