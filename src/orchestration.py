from __future__ import annotations

from pathlib import Path

from src.graph import build_graph


def create_workflow(prompts_dir: str = "prompts", outputs_dir: str = "outputs", allow_mock_llm: bool = False):
    """Return compiled LangGraph workflow used by main entrypoint."""
    return build_graph(prompts_dir=Path(prompts_dir), outputs_dir=Path(outputs_dir), allow_mock_llm=allow_mock_llm)
