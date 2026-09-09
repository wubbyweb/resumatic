"""
agents/orchestrator.py
----------------------
Agent 1: Orchestrator (Supervisor)

Role: Central coordinator for the multi-agent pipeline.
LLM:  Yes — uses an LLM to log step progress and handle errors gracefully.

Responsibilities:
  1. Validate that inputs (resume file path + job description) are present.
  2. Advance the `current_step` state variable to control routing.
  3. After each worker completes, check for errors and decide whether to
     continue or terminate early.
  4. Signal pipeline completion by setting current_step = "done".

Routing (deterministic via LangGraph conditional edges in graph.py):
  current_step == "extract"   → extractor node
  current_step == "enhance"   → enhancer node
  current_step == "generate"  → pdf_generator node
  current_step == "done"      → END
"""

import os

from langchain_core.messages import HumanMessage, SystemMessage

from llm_factory import get_llm
from state import ResumaticState

# ---------------------------------------------------------------------------
# System prompt for the Orchestrator LLM
# ---------------------------------------------------------------------------
ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for a resume tailoring pipeline.
Your job is to coordinate three specialist workers in sequence:

  1. Resume Extractor  — extracts structured content from the user's resume file (no LLM).
  2. Content Enhancer  — rewrites and tailors the content to match a target job description (LLM).
  3. PDF Generator     — converts the enhanced content into a professional PDF resume (no LLM).

At each step you will receive a status update. Acknowledge it with a brief, encouraging
one-sentence message (e.g. "Extraction complete — moving on to content enhancement.").
If an error is reported, acknowledge it clearly and state that the pipeline has stopped.
Keep your messages short and professional."""


def _get_llm():
    """Delegate to the shared LLM factory (OpenRouter, Orchestrator model)."""
    return get_llm("orchestrator", temperature=0.0)


# ---------------------------------------------------------------------------
# Orchestrator node
# ---------------------------------------------------------------------------

def orchestrator_node(state: ResumaticState) -> dict:
    """
    The Orchestrator decides what to do next based on the current pipeline step.

    On each call it:
      - Checks for errors from the previous worker.
      - Advances `current_step` to trigger the next worker.
      - Uses the LLM to produce a human-readable status message (stored in messages).
    """
    llm = _get_llm()

    # --- Initial validation (first call only, current_step is not yet set) ---
    if not state.get("current_step"):
        if not state.get("resume_file_path") or not os.path.exists(state["resume_file_path"]):
            return {
                "current_step": "done",
                "error": "Resume file not found. Please upload a valid PDF or DOCX file.",
                "messages": state.get("messages", []),
            }
        if not state.get("job_description", "").strip():
            return {
                "current_step": "done",
                "error": "Job description is empty. Please provide a job description.",
                "messages": state.get("messages", []),
            }
        # First entry — kick off extraction
        next_step = "extract"
        status_msg = "Inputs validated. Starting resume extraction."

    else:
        current = state["current_step"]

        # --- Error guard: if a worker set an error, stop the pipeline ---
        if state.get("error"):
            llm_response = llm.invoke([
                SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
                HumanMessage(content=f"Error encountered: {state['error']}"),
            ])
            return {
                "current_step": "done",
                "messages": state.get("messages", []) + [llm_response.content],
            }

        # --- Advance the step based on what just completed ---
        if current == "extract":
            next_step = "enhance"
            status_msg = "Extraction complete. Handing off to the Content Enhancer."
        elif current == "enhance":
            next_step = "generate"
            status_msg = "Enhancement complete. Handing off to the PDF Generator."
        elif current == "generate":
            next_step = "done"
            status_msg = "PDF generation complete. Tailored resume is ready."
        else:
            # Already done
            next_step = "done"
            status_msg = "Pipeline already complete."

    # --- Use the LLM to produce a status acknowledgement ---
    llm_response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
        HumanMessage(content=status_msg),
    ])

    updated_messages = state.get("messages", []) + [llm_response.content]

    print(f"[Orchestrator] {status_msg}")

    return {
        "current_step": next_step,
        "messages": updated_messages,
    }


# ---------------------------------------------------------------------------
# Routing function (used by graph.py add_conditional_edges)
# ---------------------------------------------------------------------------

def route_based_on_step(state: ResumaticState) -> str:
    """
    Reads current_step from state and returns the name of the next node.
    This function is passed to add_conditional_edges() in graph.py.
    """
    step = state.get("current_step", "done")
    return step  # "extract" | "enhance" | "generate" | "done"
