"""
agents/enhancer.py
------------------
Agent 3: Content Enhancer

Role:  Tailor the extracted resume content to match the target job description.
LLM:   YES — this is the core AI-powered agent.

Responsibilities:
  1. Analyse the job description for key requirements, keywords, and skills.
  2. Rewrite the professional summary to align with the target role.
  3. Enhance experience bullet points — emphasise relevant achievements and
     naturally incorporate job-description keywords.
  4. Reorder skills to prioritise those mentioned in the job description.
  5. NEVER fabricate experience, skills, or credentials that don't already
     exist in the extracted resume.

Uses LangChain's `with_structured_output()` to guarantee the LLM returns
a JSON object that conforms exactly to the ResumeData schema.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List
from state import ResumaticState
from llm_factory import get_llm


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------
# LangChain's with_structured_output() uses these to constrain the LLM
# response into a validated, typed object — no manual JSON parsing needed.

class ExperienceEntryModel(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Employer name")
    duration: str = Field(description="Employment duration e.g. 'Jan 2022 – Present'")
    bullets: List[str] = Field(description="Achievement / responsibility bullet points")


class EducationEntryModel(BaseModel):
    degree: str = Field(description="Degree name e.g. 'B.S. Computer Science'")
    institution: str = Field(description="School or university name")
    year: str = Field(description="Graduation year or date range")


class ProjectEntryModel(BaseModel):
    name: str = Field(description="Project title")
    description: str = Field(description="Short description of the project")


class ResumeDataModel(BaseModel):
    """Structured output schema — must match ResumeData in state.py."""
    name: str = Field(description="Candidate full name")
    email: str = Field(description="Contact email address")
    phone: str = Field(description="Contact phone number")
    linkedin: str = Field(description="LinkedIn profile URL")
    summary: str = Field(description="Professional summary tailored to the target role")
    skills: List[str] = Field(description="Skills list, prioritised by job-description relevance")
    experience: List[ExperienceEntryModel] = Field(description="Work experience entries")
    education: List[EducationEntryModel] = Field(description="Education entries")
    certifications: List[str] = Field(description="Certifications and licences")
    projects: List[ProjectEntryModel] = Field(description="Projects")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ENHANCER_SYSTEM_PROMPT = """You are an expert resume writer and career coach.

You will receive:
  1. A candidate's existing resume content (as a JSON object).
  2. A target job description.

Your task is to produce an enhanced version of the resume JSON that:

  1. SUMMARY — Rewrite the professional summary to directly address the target role,
     highlighting the most relevant experience and skills. Keep it to 3–4 sentences.

  2. EXPERIENCE BULLETS — For each job entry, rewrite and enhance the bullet points to:
       - Lead with strong action verbs.
       - Emphasise achievements that are most relevant to the job description.
       - Naturally incorporate keywords and technologies from the job description
         where they genuinely apply to the candidate's background.
       - Quantify impact where possible (use existing numbers; do not invent them).

  3. SKILLS — Reorder the skills list so that skills mentioned in the job description
     appear first. Do not add new skills that don't exist in the original resume.

  4. PRESERVATION RULES (strictly enforced):
       - NEVER fabricate experience, job titles, companies, dates, degrees, or certifications.
       - NEVER add skills the candidate did not already have.
       - Keep all factual information (names, dates, companies, institutions) exactly as given.
       - The output JSON must have the same structure as the input JSON.

Return ONLY the enhanced resume as a structured JSON object matching the schema."""


# ---------------------------------------------------------------------------
# LLM initialisation
# ---------------------------------------------------------------------------

def _get_llm():
    """Delegate to the shared LLM factory (OpenRouter, Enhancer model)."""
    return get_llm("enhancer", temperature=0.3)


# ---------------------------------------------------------------------------
# Enhancer node
# ---------------------------------------------------------------------------

def enhancer_node(state: ResumaticState) -> dict:
    """
    Agent 3 — Content Enhancer node.

    Reads extracted_resume and job_description from state, invokes the LLM
    with structured output, and writes the result to state["enhanced_resume"].

    Uses two strategies:
      1. with_structured_output() — preferred, works on most capable models.
      2. Raw LLM call + JSON fence stripping + Pydantic validation — fallback
         for models that wrap JSON in markdown code fences.
    """
    print("[Enhancer] Starting content enhancement...")

    extracted_resume = state.get("extracted_resume")
    job_description = state.get("job_description", "")

    if not extracted_resume:
        return {"error": "Enhancer received empty extracted_resume."}

    try:
        llm = _get_llm()

        messages = [
            SystemMessage(content=ENHANCER_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"## Candidate's Current Resume (JSON)\n\n"
                f"```json\n{json.dumps(extracted_resume, indent=2)}\n```\n\n"
                f"## Target Job Description\n\n{job_description}\n\n"
                f"Return ONLY valid JSON — no markdown fences, no explanation."
            )),
        ]

        # --- Strategy 1: with_structured_output ---
        try:
            structured_llm = llm.with_structured_output(ResumeDataModel)
            response: ResumeDataModel = structured_llm.invoke(messages)
            enhanced_resume = response.model_dump()
            print("[Enhancer] Used structured output strategy.")

        except Exception as struct_err:
            # --- Strategy 2: Raw call + fence stripping + Pydantic validation ---
            print(f"[Enhancer] Structured output failed ({type(struct_err).__name__}), "
                  "falling back to raw JSON parsing...")

            raw = llm.invoke(messages)
            text = raw.content if hasattr(raw, "content") else str(raw)

            # Strip ```json ... ``` or ``` ... ``` fences
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)
            validated = ResumeDataModel.model_validate(data)
            enhanced_resume = validated.model_dump()
            print("[Enhancer] Used raw JSON fallback strategy.")

        print(f"[Enhancer] Enhancement complete. "
              f"Summary length: {len(enhanced_resume.get('summary', ''))} chars.")

        return {"enhanced_resume": enhanced_resume}

    except Exception as exc:
        print(f"[Enhancer] ERROR: {exc}")
        return {"error": f"Enhancer failed: {str(exc)}"}
