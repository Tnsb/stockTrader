from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from groq import Groq
from pydantic import BaseModel


class EvaluatorResult(BaseModel):
    agents_agree: bool
    analysis: str


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Evaluator output did not contain JSON.")
    return json.loads(text[start : end + 1])


class Evaluator:
    def __init__(self, prompts_dir: Path, model: str | None = None, allow_mock: bool = False) -> None:
        api_key = os.getenv("GROQ_API_KEY", "")
        self.mock_mode = allow_mock and not api_key
        self.client = Groq(api_key=api_key) if api_key else None
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.prompt = (prompts_dir / "evaluator.txt").read_text(encoding="utf-8").strip()
        if not api_key and not self.mock_mode:
            raise EnvironmentError("Missing GROQ_API_KEY. Add it to your environment or use --mock-llm.")

    def evaluate(
        self,
        ticker: str,
        market_data: Dict[str, Any],
        strategy_a: Dict[str, Any],
        strategy_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        agree = strategy_a["decision"] == strategy_b["decision"]
        if self.mock_mode:
            if agree:
                analysis = (
                    f"Both strategies converge on {strategy_a['decision']} for {ticker} because recent signals "
                    f"do not strongly separate trend-following from mean-reversion interpretations. "
                    f"Momentum and contrarian confidence scores ({strategy_a['confidence']} and {strategy_b['confidence']}) "
                    f"are directionally aligned."
                )
            else:
                analysis = (
                    f"The strategies diverge because Momentum weights trend continuation while Contrarian looks for overreaction. "
                    f"Recent move ({market_data['pct_change_30d']}%), RSI ({market_data['rsi_14']}), and drawdown "
                    f"({market_data['recent_drawdown_90d_pct']}%) support different behavioral conclusions."
                )
            return EvaluatorResult(agents_agree=agree, analysis=analysis).model_dump()

        payload = {
            "ticker": ticker,
            "market_data": market_data,
            "strategy_a": strategy_a,
            "strategy_b": strategy_b,
            "agents_agree": agree,
            "required_json_schema": {
                "agents_agree": agree,
                "analysis": "If agree: concise consensus summary. If disagree: explain philosophical and indicator-level divergence in 3-5 sentences.",
            },
        }
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        parsed = _extract_json(content)
        parsed["agents_agree"] = bool(agree)
        result = EvaluatorResult.model_validate(parsed)
        return result.model_dump()
