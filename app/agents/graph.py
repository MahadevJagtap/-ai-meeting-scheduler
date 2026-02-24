"""
LangGraph StateGraph assembly for the scheduling workflow.
"""

from __future__ import annotations

import logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    analyze_request,
    execute_scheduling,
    retrieve_context,
    synthesize_slots,
)
from app.agents.state import AgentState
from app.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def _should_continue_after_synthesis(state: AgentState) -> str:
    """Conditional edge after synthesize_slots."""
    status = state.get("status", "")
    if status == "scheduling" and state.get("selected_slot"):
        return "execute_scheduling"
    elif status == "synthesizing" and state.get("retry_count", 0) < 3:
        return "synthesize_slots"
    else:
        return END


def _should_continue_after_analysis(state: AgentState) -> str:
    """Proceed to retrieval unless analysis failed."""
    if state.get("status") == "error":
        return END
    return "retrieve_context"


# ── Persistence Helper ──────────────────────────────────────────

async def get_checkpointer():
    """Returns a MemorySaver for testing."""
    return MemorySaver()


def build_scheduling_graph() -> StateGraph:
    """Construct and return the StateGraph for meeting scheduling."""
    graph = StateGraph(AgentState)

    graph.add_node("analyze_request", analyze_request)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("synthesize_slots", synthesize_slots)
    graph.add_node("execute_scheduling", execute_scheduling)

    graph.set_entry_point("analyze_request")

    graph.add_conditional_edges(
        "analyze_request",
        _should_continue_after_analysis,
        {
            "retrieve_context": "retrieve_context",
            END: END,
        },
    )

    graph.add_edge("retrieve_context", "synthesize_slots")

    graph.add_conditional_edges(
        "synthesize_slots",
        _should_continue_after_synthesis,
        {
            "execute_scheduling": "execute_scheduling",
            "synthesize_slots": "synthesize_slots",
            END: END,
        },
    )

    graph.add_edge("execute_scheduling", END)

    logger.info("Scheduling graph built")
    return graph


# ── Compiled graph singleton ──────────────────────────────────

_base_graph = build_scheduling_graph()


async def run_workflow(state: AgentState, thread_id: str) -> AgentState:
    """Run the workflow with persistence using MemorySaver."""
    checkpointer = await get_checkpointer()
    compiled_graph = _base_graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    return await compiled_graph.ainvoke(state, config=config)
