from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def build_summary(stock_payloads: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    agreements = 0
    tickers: List[str] = []
    strategies: List[str] = []

    for payload in stock_payloads:
        ticker = payload["ticker"]
        tickers.append(ticker)
        if not strategies:
            strategies = [payload["strategy_a"]["name"], payload["strategy_b"]["name"]]
        agree = bool(payload["evaluator"]["agents_agree"])
        if agree:
            agreements += 1
        rows.append(
            {
                "ticker": ticker,
                "a_decision": payload["strategy_a"]["decision"],
                "b_decision": payload["strategy_b"]["decision"],
                "agree": agree,
            }
        )

    return {
        "strategies": strategies,
        "stocks_analyzed": tickers,
        "total_agreements": agreements,
        "total_disagreements": max(0, len(rows) - agreements),
        "results": rows,
    }
