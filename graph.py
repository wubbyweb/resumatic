"""
graph.py
--------
Builds and compiles the Resumatic LangGraph StateGraph.

Graph topology (Supervisor-Worker pattern):
  - Entry point: orchestrator
  - Orchestrator uses conditional edges to route to each worker in sequence.
  - All workers return control to the orchestrator after completing.
  - The pipeline ends when orchestrator sets current_step = "done".

  orchestrator ──(extract)──► extractor ──► orchestrator
  orchestrator ──(enhance)──► enhancer  ──► orchestrator
  orchestrator ──(generate)─► pdf_generator ──► orchestrator
  orchestrator ──(done)─────► END

This module is imported by main.py. The compiled graph is a singleton
that is reused across all API requests.
"""

from langgraph.graph import END, StateGraph

from agents import (
    enhancer_node,
    extractor_node,
    orchestrator_node,
    pdf_generator_node,
    route_based_on_step,
)
from state import ResumaticState


def build_graph():
    """
    Construct and compile the Resumatic StateGraph.

    Returns a compiled LangGraph application ready to be invoked
    with an initial ResumaticState dict.
    """
    graph = StateGraph(ResumaticState)

    # -----------------------------------------------------------------------
    # Register nodes (one per agent)
    # -----------------------------------------------------------------------
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("extractor",    extractor_node)
    graph.add_node("enhancer",     enhancer_node)
    graph.add_node("pdf_generator", pdf_generator_node)

    # -----------------------------------------------------------------------
    # Entry point — the Orchestrator is always called first
    # -----------------------------------------------------------------------
    graph.set_entry_point("orchestrator")

    # -----------------------------------------------------------------------
    # Conditional routing FROM the Orchestrator
    # route_based_on_step() reads state["current_step"] and returns a key:
    #   "extract"  → extractor node
    #   "enhance"  → enhancer node
    #   "generate" → pdf_generator node
    #   "done"     → END
    # -----------------------------------------------------------------------
    graph.add_conditional_edges(
        "orchestrator",
        route_based_on_step,
        {
            "extract":  "extractor",
            "enhance":  "enhancer",
            "generate": "pdf_generator",
            "done":     END,
        },
    )

    # -----------------------------------------------------------------------
    # All workers return to the Orchestrator after completing
    # -----------------------------------------------------------------------
    graph.add_edge("extractor",     "orchestrator")
    graph.add_edge("enhancer",      "orchestrator")
    graph.add_edge("pdf_generator", "orchestrator")

    # -----------------------------------------------------------------------
    # Compile and return the executable graph
    # -----------------------------------------------------------------------
    return graph.compile()


# Singleton compiled graph — built once at module import time.
resumatic_graph = build_graph()
