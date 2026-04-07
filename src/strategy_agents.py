from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Literal

from groq import Groq
from pydantic import BaseModel, Field, ValidationError


Decision = Literal["BUY", "HOLD", "SELL"]


class StrategyResult(BaseModel):
    name: str
    decision: Decision
    confidence: int = Field(ge=1, le=10)
    justification: str = Field(min_length=20)


def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM output did not contain JSON object.")
        return json.loads(text[start : end + 1])


class StrategyAgentRunner:
    def __init__(self, prompts_dir: Path, model: str | None = None, allow_mock: bool = False) -> None:
        api_key = os.getenv("GROQ_API_KEY", "")
        self.mock_mode = allow_mock and not api_key
        self.client = Groq(api_key=api_key) if api_key else None
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.prompts_dir = prompts_dir
        if not api_key and not self.mock_mode:
            raise EnvironmentError("Missing GROQ_API_KEY. Add it to your environment or use --mock-llm.")

    def _call_model(self, system_prompt: str, market_data: Dict[str, Any], strategy_name: str) -> StrategyResult:
        user_payload = {
            "task": "Analyze this stock under your strategy philosophy and return strict JSON.",
            "required_json_schema": {
                "name": strategy_name,
                "decision": "BUY | HOLD | SELL",
                "confidence": "integer 1..10",
                "justification": "3-5 sentences referencing specific numeric fields from market_data",
            },
            "market_data": market_data,
        }
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        raw = _extract_json(content)
        raw["name"] = strategy_name
        try:
            return StrategyResult.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Invalid strategy output for {strategy_name}: {exc}") from exc

    def run_strategy_a(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return _mock_momentum_response(market_data)
        system_prompt = _read_prompt(self.prompts_dir / "strategy_a.txt")
        result = self._call_model(system_prompt, market_data, strategy_name="Momentum Trader")
        return result.model_dump()

    def run_strategy_b(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return _mock_contrarian_response(market_data)
        system_prompt = _read_prompt(self.prompts_dir / "strategy_b.txt")
        result = self._call_model(system_prompt, market_data, strategy_name="Value Contrarian")
        return result.model_dump()

    def run_debate_rebuttal(
        self,
        strategy_name: str,
        original_prompt_file: str,
        own_output: Dict[str, Any],
        opponent_output: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.mock_mode:
            return _mock_rebuttal(strategy_name, own_output, opponent_output, market_data)
        strategy_prompt = _read_prompt(self.prompts_dir / original_prompt_file)
        debate_prompt = _read_prompt(self.prompts_dir / "debate_rebuttal.txt")
        system_prompt = strategy_prompt + "\n\n" + debate_prompt
        payload = {
            "task": "Respond to the opposing strategy's reasoning. You may revise or maintain your position.",
            "your_original_analysis": own_output,
            "opponent_analysis": opponent_output,
            "market_data": market_data,
            "required_json_schema": {
                "revised_decision": "BUY | HOLD | SELL",
                "revised_confidence": "integer 1..10",
                "rebuttal": "3-5 sentences responding to the opponent",
            },
        }
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        raw = _extract_json(content)
        raw["name"] = strategy_name
        return DebateResult.model_validate(raw).model_dump()


class DebateResult(BaseModel):
    name: str
    revised_decision: Decision
    revised_confidence: int = Field(ge=1, le=10)
    rebuttal: str = Field(min_length=20)


def _mock_rebuttal(
    strategy_name: str,
    own_output: Dict[str, Any],
    opponent_output: Dict[str, Any],
    market_data: Dict[str, Any],
) -> Dict[str, Any]:
    opp_decision = opponent_output["decision"]
    own_decision = own_output["decision"]
    rebuttal = (
        f"The opposing {opponent_output['name']} recommends {opp_decision}, but my indicators "
        f"still support {own_decision}. The 30-day change of {market_data['pct_change_30d']}% "
        f"and RSI of {market_data['rsi_14']} reinforce my original thesis. "
        f"I maintain my position with unchanged conviction."
    )
    return DebateResult(
        name=strategy_name,
        revised_decision=own_decision,
        revised_confidence=own_output["confidence"],
        rebuttal=rebuttal,
    ).model_dump()


def _mock_momentum_response(market_data: Dict[str, Any]) -> Dict[str, Any]:
    price = market_data["current_price"]
    ma20 = market_data["moving_avg_20d"]
    ma50 = market_data["moving_avg_50d"]
    pct_30d = market_data["pct_change_30d"]
    vol_ratio = market_data["volume_trend_ratio_10d_over_prev20d"]
    vol = market_data["volatility_30d"]
    if price > ma20 > ma50 and pct_30d > 3 and vol_ratio >= 1.0:
        decision, conf = "BUY", 8
    elif price < ma20 < ma50 and pct_30d < -3:
        decision, conf = "SELL", 7
    else:
        decision, conf = "HOLD", 6
    justification = (
        f"Price is {price} versus MA20 {ma20} and MA50 {ma50}, with a 30-day move of {pct_30d}%. "
        f"Volume trend ratio is {vol_ratio}, which helps confirm whether momentum is broadening or fading. "
        f"Recent volatility is {vol}, so conviction is adjusted for choppiness. "
        f"Given these trend-following signals, the momentum stance is {decision}."
    )
    return StrategyResult(
        name="Momentum Trader",
        decision=decision,  # type: ignore[arg-type]
        confidence=conf,
        justification=justification,
    ).model_dump()


def _mock_contrarian_response(market_data: Dict[str, Any]) -> Dict[str, Any]:
    pct_30d = market_data["pct_change_30d"]
    dist_high = market_data["distance_from_52w_high_pct"]
    dist_low = market_data["distance_from_52w_low_pct"]
    dd_90d = market_data["recent_drawdown_90d_pct"]
    rsi = market_data["rsi_14"]
    if dd_90d < -15 and rsi < 35 and dist_high < -20:
        decision, conf = "BUY", 8
    elif pct_30d > 12 and rsi > 70 and dist_high > -5:
        decision, conf = "SELL", 7
    else:
        decision, conf = "HOLD", 6
    justification = (
        f"The stock is {dist_high}% from its 52-week high and {dist_low}% above its 52-week low, "
        f"with a 90-day drawdown of {dd_90d}%. "
        f"RSI is {rsi} and the 30-day move is {pct_30d}%, which helps detect overreaction in either direction. "
        f"Under a mean-reversion lens, this supports a {decision} view."
    )
    return StrategyResult(
        name="Value Contrarian",
        decision=decision,  # type: ignore[arg-type]
        confidence=conf,
        justification=justification,
    ).model_dump()
