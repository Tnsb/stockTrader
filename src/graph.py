from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from src.evaluator import Evaluator
from src.io_utils import write_json
from src.market_data import fetch_market_data_summary
from src.strategy_agents import StrategyAgentRunner


class GraphState(TypedDict, total=False):
    ticker: str
    run_date: str
    market_data_summary: Dict[str, Any]
    strategy_a: Dict[str, Any]
    strategy_b: Dict[str, Any]
    evaluator: Dict[str, Any]
    debate_a: Dict[str, Any]
    debate_b: Dict[str, Any]
    branch: Literal["consensus", "disagreement"]
    output_path: str
    error: str


def build_graph(prompts_dir: Path, outputs_dir: Path, allow_mock_llm: bool = False):
    strategy_runner = StrategyAgentRunner(prompts_dir=prompts_dir, allow_mock=allow_mock_llm)
    evaluator = Evaluator(prompts_dir=prompts_dir, allow_mock=allow_mock_llm)

    def market_data_node(state: GraphState) -> GraphState:
        ticker = state["ticker"].upper()
        summary = fetch_market_data_summary(ticker)
        return {
            "ticker": ticker,
            "run_date": summary["run_date"],
            "market_data_summary": summary,
        }

    def strategy_a_node(state: GraphState) -> GraphState:
        result = strategy_runner.run_strategy_a(state["market_data_summary"])
        return {"strategy_a": result}

    def strategy_b_node(state: GraphState) -> GraphState:
        result = strategy_runner.run_strategy_b(state["market_data_summary"])
        return {"strategy_b": result}

    def evaluator_node(state: GraphState) -> GraphState:
        result = evaluator.evaluate(
            ticker=state["ticker"],
            market_data=state["market_data_summary"],
            strategy_a=state["strategy_a"],
            strategy_b=state["strategy_b"],
        )
        return {"evaluator": result}

    def route_after_eval(state: GraphState) -> str:
        return "consensus" if state["evaluator"]["agents_agree"] else "disagreement"

    def consensus_node(_: GraphState) -> GraphState:
        return {"branch": "consensus"}

    def disagreement_node(_: GraphState) -> GraphState:
        return {"branch": "disagreement"}

    def debate_a_rebuttal_node(state: GraphState) -> GraphState:
        rebuttal_a = strategy_runner.run_debate_rebuttal(
            strategy_name="Momentum Trader",
            original_prompt_file="strategy_a.txt",
            own_output=state["strategy_a"],
            opponent_output=state["strategy_b"],
            market_data=state["market_data_summary"],
        )
        return {"debate_a": rebuttal_a}

    def debate_b_rebuttal_node(state: GraphState) -> GraphState:
        rebuttal_b = strategy_runner.run_debate_rebuttal(
            strategy_name="Value Contrarian",
            original_prompt_file="strategy_b.txt",
            own_output=state["strategy_b"],
            opponent_output=state["strategy_a"],
            market_data=state["market_data_summary"],
        )
        return {"debate_b": rebuttal_b}

    def save_output_node(state: GraphState) -> GraphState:
        payload = {
            "ticker": state["ticker"],
            "run_date": state["run_date"],
            "market_data_summary": state["market_data_summary"],
            "strategy_a": state["strategy_a"],
            "strategy_b": state["strategy_b"],
            "evaluator": state["evaluator"],
        }
        if state.get("debate_a") or state.get("debate_b"):
            payload["debate"] = {
                "momentum_rebuttal": state.get("debate_a", {}),
                "contrarian_rebuttal": state.get("debate_b", {}),
            }
        output_path = outputs_dir / f"{state['ticker']}.json"
        write_json(output_path, payload)
        return {"output_path": str(output_path)}

    workflow = StateGraph(GraphState)
    workflow.add_node("market_data_node", market_data_node)
    workflow.add_node("strategy_a_node", strategy_a_node)
    workflow.add_node("strategy_b_node", strategy_b_node)
    workflow.add_node("evaluator_node", evaluator_node)
    workflow.add_node("consensus_node", consensus_node)
    workflow.add_node("disagreement_node", disagreement_node)
    workflow.add_node("debate_a_rebuttal_node", debate_a_rebuttal_node)
    workflow.add_node("debate_b_rebuttal_node", debate_b_rebuttal_node)
    workflow.add_node("save_output_node", save_output_node)

    workflow.add_edge(START, "market_data_node")
    workflow.add_edge("market_data_node", "strategy_a_node")
    workflow.add_edge("market_data_node", "strategy_b_node")
    workflow.add_edge("strategy_a_node", "evaluator_node")
    workflow.add_edge("strategy_b_node", "evaluator_node")
    workflow.add_conditional_edges(
        "evaluator_node",
        route_after_eval,
        {
            "consensus": "consensus_node",
            "disagreement": "disagreement_node",
        },
    )
    workflow.add_edge("consensus_node", "save_output_node")
    workflow.add_edge("disagreement_node", "debate_a_rebuttal_node")
    workflow.add_edge("disagreement_node", "debate_b_rebuttal_node")
    workflow.add_edge("debate_a_rebuttal_node", "save_output_node")
    workflow.add_edge("debate_b_rebuttal_node", "save_output_node")
    workflow.add_edge("save_output_node", END)

    return workflow.compile()
