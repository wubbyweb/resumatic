"""
graph.py
--------
Builds and compiles the Resumatic LangGraph StateGraph.

Graph topology (Supervisor-Worker pattern with Enhancer feedback loop):
  - Entry point: orchestrator
  - Orchestrator uses conditional edges to route to each worker in sequence.
  - All workers return control to the orchestrator after completing,
    EXCEPT the enhancer — it first passes through the enhancement_critic.
  - The enhancement_critic runs a quality check and either:
      • advances to the orchestrator (pass, or retries exhausted), or
      • loops back to the enhancer with written feedback (fail, retry available).
  - The pipeline ends when orchestrator sets current_step = "done".

  orchestrator ──(extract)──► extractor ──────────────────────► orchestrator
  orchestrator ──(enhance)──► enhancer ──► enhancement_critic ──(advance)──► orchestrator
                                 ▲                              └──(retry)──► enhancer
  orchestrator ──(generate)─► pdf_generator ──────────────────► orchestrator
  orchestrator ──(done)─────► END

This module is imported by main.py. The compiled graph is a singleton
that is reused across all API requests.
"""

from langgraph.graph import END, StateGraph

from agents import (
    enhancement_critic_node,
    enhancer_node,
    extractor_node,
    orchestrator_node,
    pdf_generator_node,
    route_after_critic,
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
    graph.add_node("orchestrator",        orchestrator_node)
    graph.add_node("extractor",           extractor_node)
    graph.add_node("enhancer",            enhancer_node)
    graph.add_node("enhancement_critic",  enhancement_critic_node)
    graph.add_node("pdf_generator",       pdf_generator_node)

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
    # Extractor and PDF generator return directly to the Orchestrator
    # -----------------------------------------------------------------------
    graph.add_edge("extractor",     "orchestrator")
    graph.add_edge("pdf_generator", "orchestrator")

    # -----------------------------------------------------------------------
    # Enhancer → Enhancement Critic (always, on every run)
    # -----------------------------------------------------------------------
    graph.add_edge("enhancer", "enhancement_critic")

    # -----------------------------------------------------------------------
    # Enhancement Critic conditional routing
    # route_after_critic() reads enhance_critique and enhance_iteration:
    #   "retry"   → enhancer  (critic failed, retries remaining)
    #   "advance" → orchestrator (critic passed, or retries exhausted)
    # -----------------------------------------------------------------------
    graph.add_conditional_edges(
        "enhancement_critic",
        route_after_critic,
        {
            "retry":   "enhancer",
            "advance": "orchestrator",
        },
    )

    # -----------------------------------------------------------------------
    # Compile and return the executable graph
    # -----------------------------------------------------------------------
    return graph.compile()


# Singleton compiled graph — built once at module import time.
resumatic_graph = build_graph()
