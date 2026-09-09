"""
state.py
--------
Shared state schema for the Resumatic multi-agent pipeline.

All agents read from and write to a single ResumaticState object
managed by LangGraph's StateGraph. This is the central data contract
that connects every agent in the pipeline.
"""

from typing import TypedDict

# ---------------------------------------------------------------------------
# Resume Data Schema
# ---------------------------------------------------------------------------
# This schema is used for both `extracted_resume` (Agent 2 output) and
# `enhanced_resume` (Agent 3 output). The structure is identical — Agent 3
# enriches the content without changing the shape of the data.

class ExperienceEntry(TypedDict):
    title: str           # Job title
    company: str         # Employer name
    duration: str        # e.g. "Jan 2022 – Present"
    bullets: list[str]   # Achievement / responsibility bullet points


class EducationEntry(TypedDict):
    degree: str          # e.g. "B.S. Computer Science"
    institution: str     # School / university name
    year: str            # Graduation year or date range


class ProjectEntry(TypedDict):
    name: str            # Project title
    description: str     # Short description of what was built / achieved


class ResumeData(TypedDict):
    name: str                        # Candidate full name
    email: str                       # Contact email
    phone: str                       # Contact phone
    linkedin: str                    # LinkedIn URL (may be empty string)
    summary: str                     # Professional summary / objective
    skills: list[str]                # Flat list of skills
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    certifications: list[str]        # e.g. ["AWS Solutions Architect", ...]
    projects: list[ProjectEntry]


# ---------------------------------------------------------------------------
# Pipeline State
# ---------------------------------------------------------------------------
# LangGraph reads this TypedDict to manage shared state across all nodes.

class ResumaticState(TypedDict):
    # --- Inputs (populated by the FastAPI endpoint before invoking the graph) ---
    resume_file_path: str      # Absolute path to the uploaded resume file (PDF/DOCX)
    job_description: str       # Raw job description text submitted by the user

    # --- Agent 2 output ---
    extracted_resume: ResumeData | None   # Structured data parsed from the resume

    # --- Agent 3 output ---
    enhanced_resume: ResumeData | None    # Tailored resume content

    # --- Agent 4 output ---
    output_pdf_path: str       # Absolute path to the generated PDF

    # --- Orchestration ---
    messages: list             # Message history for the Orchestrator LLM
    current_step: str          # Workflow cursor: "extract" → "enhance" → "generate" → "done"
    error: str | None       # Set by any agent on failure; Orchestrator checks this
