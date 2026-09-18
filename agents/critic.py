"""
agents/critic.py
----------------
Enhancement Critic Agent

Role:  Validate the Enhancer's output before it advances to PDF generation.
LLM:   YES — used only for keyword alignment / bullet quality scoring.
       Company-name and job-count checks are pure Python (no LLM needed).

Responsibilities:
  1. Hard-check: Every company name in enhanced_resume must exactly match the
     corresponding entry in extracted_resume (positional, case-sensitive).
  2. Hard-check: The number of experience entries must be the same in both.
  3. Soft LLM check: Keyword alignment between the enhanced content and the job
     description, plus overall bullet point quality.

Return semantics (via state patch):
  - enhance_critique = None            -> passed; graph advances to orchestrator
  - enhance_critique = "<text>"        -> failed; graph retries the Enhancer
                                         (up to max_enhance_iterations)

Routing function `route_after_critic` is consumed by graph.py.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from audit_logger import log_audit
from llm_factory import get_llm
from state import ResumaticState

# ---------------------------------------------------------------------------
# Critic system prompt (soft LLM check only)
# ---------------------------------------------------------------------------

CRITIC_SYSTEM_PROMPT = """You are a strict resume quality reviewer.

You will receive:
  1. An enhanced resume (JSON) produced by an AI writer.
  2. The target job description.

Your task is to evaluate the enhanced resume on TWO dimensions only:

  A. KEYWORD ALIGNMENT -- Does the summary and experience bullets naturally
     incorporate the most important skills, technologies, and responsibilities
     from the job description? Aim for coverage of the top 5-7 key terms.

  B. BULLET QUALITY -- Are the bullets action-verb-led, specific, and impactful?
     Weak bullets are vague ("Worked on backend"), missing numbers where they
     existed in the original, or simply paraphrased job duties.

Respond with EXACTLY this format (no extra text):

VERDICT: PASS
CRITIQUE: None

-- OR --

VERDICT: FAIL
CRITIQUE: <concise, specific feedback under 120 words telling the writer exactly
           what to fix -- name specific bullets or sections>

Be strict but fair. Only FAIL if there are genuine, fixable issues that would
meaningfully improve the resume for this specific job description."""


# ---------------------------------------------------------------------------
# Hard checks (pure Python -- no LLM)
# ---------------------------------------------------------------------------

def _check_company_names(
    extracted: list,
    enhanced: list,
) -> "str | None":
    """
    Compare company fields positionally between extracted and enhanced experience.

    Returns None if all match, or a human-readable critique string if any differ.
    The comparison is stripped but case-sensitive -- we want exact preservation,
    not fuzzy matching.
    """
    mismatches = []
    for i, (orig, enh) in enumerate(zip(extracted, enhanced)):
        orig_company = (orig.get("company") or "").strip()
        enh_company  = (enh.get("company") or "").strip()
        if orig_company and orig_company != enh_company:
            mismatches.append(
                f"  Entry {i + 1}: expected company '{orig_company}', "
                f"got '{enh_company}'"
            )

    if mismatches:
        return (
            "COMPANY NAME MISMATCH -- the following experience entries have incorrect "
            "company names. You MUST copy the company name exactly from the original "
            "extracted resume JSON (verbatim, do not describe or paraphrase the company):\n"
            + "\n".join(mismatches)
        )
    return None


def _check_entry_count(extracted: list, enhanced: list) -> "str | None":
    """Return a critique string if experience entry counts do not match, else None."""
    if len(enhanced) != len(extracted):
        return (
            f"EXPERIENCE ENTRY COUNT MISMATCH -- the original resume has "
            f"{len(extracted)} job entr{'y' if len(extracted) == 1 else 'ies'}, "
            f"but the enhanced resume contains {len(enhanced)}. "
            f"You must include ALL {len(extracted)} jobs in the same order."
        )
    return None


# ---------------------------------------------------------------------------
# Soft check (LLM)
# ---------------------------------------------------------------------------

def _llm_quality_check(
    enhanced_resume: dict,
    job_description: str,
) -> "tuple[bool, str | None]":
    """
    Ask the critic LLM to evaluate keyword alignment and bullet quality.

    Returns:
        (passed: bool, critique: str | None)
        critique is None when passed=True, a short feedback string when False.
    """
    import json

    llm = get_llm("critic", temperature=0.0)

    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"## Enhanced Resume (JSON)\n\n"
            f"```json\n{json.dumps(enhanced_resume, indent=2)}\n```\n\n"
            f"## Target Job Description\n\n{job_description}"
        )),
    ]

    response = llm.invoke(messages)
    text = (response.content if hasattr(response, "content") else str(response)).strip()

    # Parse the structured response
    verdict_line = ""
    critique_line = ""
    for line in text.splitlines():
        if line.startswith("VERDICT:"):
            verdict_line = line.split(":", 1)[1].strip().upper()
        elif line.startswith("CRITIQUE:"):
            critique_line = line.split(":", 1)[1].strip()

    passed = verdict_line == "PASS"
    critique = None if (passed or critique_line in ("None", "")) else critique_line
    return passed, critique


# ---------------------------------------------------------------------------
# Critic node
# ---------------------------------------------------------------------------

def enhancement_critic_node(state: ResumaticState) -> dict:
    job_id = state.get("job_id", "")
    log_audit(job_id, "enhancement_critic", "input", state)
    result = _enhancement_critic_node(state)
    log_audit(job_id, "enhancement_critic", "output", result)
    return result


def _enhancement_critic_node(state: ResumaticState) -> dict:
    """
    Validate the Enhancer's output.

    Runs hard Python checks first (company names, entry count). If those pass,
    runs the LLM quality check. Returns a state patch with:
      - enhance_critique: None (passed) or feedback string (failed)
      - enhance_iteration: incremented by 1
    """
    iteration     = state.get("enhance_iteration", 0)
    max_iter      = state.get("max_enhance_iterations", 3)
    extracted     = (state.get("extracted_resume") or {}).get("experience", [])
    enhanced_full = state.get("enhanced_resume") or {}
    enhanced_exp  = enhanced_full.get("experience", [])
    job_desc      = state.get("job_description", "")

    print(f"[Critic] Running quality check (attempt {iteration + 1}/{max_iter})...")

    # --- 1. Hard check: entry count ---
    count_critique = _check_entry_count(extracted, enhanced_exp)
    if count_critique:
        print("[Critic] FAIL (entry count mismatch) -- will retry.")
        return {
            "enhance_critique": count_critique,
            "enhance_iteration": iteration + 1,
        }

    # --- 2. Hard check: company names ---
    company_critique = _check_company_names(extracted, enhanced_exp)
    if company_critique:
        print("[Critic] FAIL (company name mismatch) -- will retry.")
        return {
            "enhance_critique": company_critique,
            "enhance_iteration": iteration + 1,
        }

    # --- 3. Soft check: LLM keyword + bullet quality ---
    try:
        passed, llm_critique = _llm_quality_check(enhanced_full, job_desc)
    except Exception as exc:
        # If the critic LLM itself fails, don't block the pipeline -- pass through.
        print(f"[Critic] LLM check error ({exc!s}) -- passing through to avoid blocking.")
        passed, llm_critique = True, None

    if passed:
        print("[Critic] PASS -- advancing to PDF generation.")
        return {
            "enhance_critique": None,
            "enhance_iteration": iteration + 1,
        }
    else:
        print(f"[Critic] FAIL (quality) -- critique: {llm_critique}")
        return {
            "enhance_critique": llm_critique,
            "enhance_iteration": iteration + 1,
        }


# ---------------------------------------------------------------------------
# Routing function (consumed by graph.py add_conditional_edges)
# ---------------------------------------------------------------------------

def route_after_critic(state: ResumaticState) -> str:
    """
    Decide whether to retry the Enhancer or advance to the Orchestrator.

    Returns:
      "retry"   -- critic failed AND we have iterations remaining
      "advance" -- critic passed OR we have exhausted all retries
    """
    critique  = state.get("enhance_critique")
    iteration = state.get("enhance_iteration", 0)
    max_iter  = state.get("max_enhance_iterations", 3)

    if critique is not None and iteration < max_iter:
        print(
            f"[Critic Router] Retrying Enhancer "
            f"(iteration {iteration}/{max_iter}, critique present)."
        )
        return "retry"

    if critique is not None:
        print(
            f"[Critic Router] Max iterations ({max_iter}) reached -- "
            "advancing with best-effort output."
        )

    return "advance"
