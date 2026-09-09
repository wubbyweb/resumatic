"""
agents/extractor.py
-------------------
Agent 2: Resume Extractor

Role:  Extract structured content from a resume file (PDF or DOCX).
LLM:   NO — pure Python parsing using PyMuPDF, python-docx, and regex.

Responsibilities:
  1. Detect file type from extension (.pdf or .docx).
  2. Extract raw text from the file.
  3. Parse raw text into the structured ResumeData schema using regex
     patterns and heuristic section-splitting.

Notes:
  - Works best on ATS-friendly, single-column resume layouts.
  - Multi-column or heavily styled resumes may produce imperfect results.
  - No external API calls are made — this agent is fully offline.
"""

import re
import os
from state import ResumaticState


# ---------------------------------------------------------------------------
# Section header keywords
# ---------------------------------------------------------------------------
# We detect section boundaries by looking for lines that match one of these
# keywords (case-insensitive, possibly surrounded by whitespace or symbols).

SECTION_HEADERS = {
    "summary":        r"(summary|objective|profile|about me|professional summary)",
    "skills":         r"(skills|technical skills|core competencies|technologies|expertise)",
    "experience":     r"(experience|work experience|employment|work history|professional experience)",
    "education":      r"(education|academic background|qualifications)",
    "certifications": r"(certifications?|licenses?|credentials?|accreditations?)",
    "projects":       r"(projects?|personal projects?|portfolio|notable projects?)",
}


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(path: str) -> str:
    """Extract raw text from a PDF file using PyMuPDF."""
    import pymupdf  # replaces deprecated `import fitz`
    doc = pymupdf.open(path)
    pages_text = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages_text)


def _extract_text_from_docx(path: str) -> str:
    """Extract raw text from a DOCX file using python-docx."""
    from docx import Document
    doc = Document(path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def _extract_raw_text(file_path: str) -> str:
    """Route to the correct extractor based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return _extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Only PDF and DOCX are supported.")


# ---------------------------------------------------------------------------
# Contact info extraction
# ---------------------------------------------------------------------------

def _extract_name(lines: list[str]) -> str:
    """Heuristic: the candidate's name is usually the first non-empty line."""
    for line in lines:
        stripped = line.strip()
        # Skip lines that look like contact info
        if stripped and not re.search(r"[@|]|\d{5}", stripped):
            # A name-like line: mostly alpha characters, spaces, hyphens
            if re.match(r"^[A-Za-z\s\-\.]{2,50}$", stripped):
                return stripped
    return ""


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"[\+]?[\d][\d\s\-\(\)\.]{6,14}[\d]", text)
    return match.group(0).strip() if match else ""


def _extract_linkedin(text: str) -> str:
    match = re.search(r"linkedin\.com/in/[\w\-]+", text, re.IGNORECASE)
    return match.group(0) if match else ""


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _split_into_sections(text: str) -> dict[str, str]:
    """
    Split the raw resume text into labelled sections based on section headers.
    Returns a dict like {"experience": "...", "skills": "...", ...}.
    The text before any recognised header is stored under "header".
    """
    lines = text.split("\n")
    sections = {}
    current_section = "header"
    buffer = []

    for line in lines:
        stripped = line.strip()
        matched_section = None

        # Check whether this line is a section header
        for section_name, pattern in SECTION_HEADERS.items():
            if re.match(rf"^\s*{pattern}\s*[:\-]?\s*$", stripped, re.IGNORECASE):
                matched_section = section_name
                break

        if matched_section:
            # Save the current buffer into the previous section
            sections[current_section] = "\n".join(buffer).strip()
            current_section = matched_section
            buffer = []
        else:
            buffer.append(line)

    # Save the last section
    sections[current_section] = "\n".join(buffer).strip()
    return sections


# ---------------------------------------------------------------------------
# Section-specific parsers
# ---------------------------------------------------------------------------

def _parse_skills(text: str) -> list[str]:
    """
    Parse a skills section. Handles comma-separated, pipe-separated,
    bullet-separated, or newline-separated skill lists.
    """
    if not text:
        return []
    # Replace bullets and pipes with commas, then split
    normalized = re.sub(r"[•\|\n\t]+", ",", text)
    skills = [s.strip() for s in normalized.split(",") if s.strip()]
    return skills


def _parse_experience(text: str) -> list[dict]:
    """
    Parse the experience section into a list of job entries.

    Handles two common PDF layouts:
      Layout A (inline):  "- Built REST APIs..."   (marker + text on same line)
      Layout B (split):   "-"                      (marker alone)
                          "Built REST APIs..."     (text on next line)

    State machine:
      - Detects job title lines via "Title - Company" or "Title — Company" separators.
      - Detects duration lines via month/year patterns.
      - Detects bullet markers (lone -, •, *) and reads the following non-marker
        line as the bullet text (handles Layout B).
      - Starts a new job entry whenever a new title/company line is detected,
        regardless of whether the current entry has any bullets yet.
    """
    if not text:
        return []

    entries = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    DURATION_PATTERN = re.compile(
        r"(\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|"
        r"march|april|june|july|august|september|october|november|december)\b.*?\d{4}"
        r"|\d{4}\s*[-–]\s*(\d{4}|present))",
        re.IGNORECASE,
    )
    # Matches a bullet marker that is either alone OR has text after a space
    INLINE_BULLET = re.compile(r"^[•\-\*]\s+(.+)")
    # Matches a lone marker with nothing after it
    LONE_MARKER   = re.compile(r"^[•\-\*]\s*$")
    # Matches "Title - Company" or "Title — Company" (job header)
    JOB_HEADER    = re.compile(r"^(.+?)\s+[-—]\s+(.+)$")

    current_entry = None
    awaiting_bullet_text = False   # True when we just saw a lone marker

    def is_job_header(line: str) -> bool:
        """Return True if this line looks like a job title + company."""
        m = JOB_HEADER.match(line)
        if not m:
            return False
        # Reject duration lines that happen to contain a dash (e.g. "Mar 2021 - Present")
        if DURATION_PATTERN.search(line):
            return False
        return True

    def start_new_entry(line: str):
        """Parse a job header line and return a fresh entry dict."""
        m = JOB_HEADER.match(line)
        if m:
            return {
                "title": m.group(1).strip(),
                "company": m.group(2).strip(),
                "duration": "",
                "bullets": [],
            }
        # Fallback: treat the whole line as the title
        return {"title": line, "company": "", "duration": "", "bullets": []}

    for line in lines:
        # --- Bullet marker alone on its own line (Layout B) ---
        if LONE_MARKER.match(line):
            awaiting_bullet_text = True
            continue

        # --- Inline bullet: "- Some text here" (Layout A) ---
        inline_match = INLINE_BULLET.match(line)
        if inline_match:
            awaiting_bullet_text = False
            if current_entry is not None:
                current_entry["bullets"].append(inline_match.group(1).strip())
            continue

        # --- Text line arriving after a lone marker (Layout B bullet text) ---
        if awaiting_bullet_text:
            awaiting_bullet_text = False
            if current_entry is not None:
                # But only if this line is not a duration or another header
                if not DURATION_PATTERN.search(line) and not is_job_header(line):
                    current_entry["bullets"].append(line)
                    continue
            # If it turned out to be something else, fall through to normal handling

        # --- Duration line ---
        if DURATION_PATTERN.search(line) and not is_job_header(line):
            if current_entry is not None:
                current_entry["duration"] = line
            continue

        # --- Job header line (new job starts here) ---
        if is_job_header(line):
            if current_entry is not None:
                entries.append(current_entry)
            current_entry = start_new_entry(line)
            awaiting_bullet_text = False
            continue

        # --- Anything else: possible second line of a company name or stray text ---
        if current_entry is not None and not current_entry.get("company"):
            current_entry["company"] = line

    # Flush the last entry
    if current_entry is not None:
        entries.append(current_entry)

    return entries



def _parse_education(text: str) -> list[dict]:
    """
    Parse the education section. Each entry is typically 2–3 lines:
      Line 1: Degree name
      Line 2: Institution name
      Line 3: Year / date range
    """
    if not text:
        return []

    YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
    entries = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        entry = {"degree": lines[i], "institution": "", "year": ""}
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if YEAR_PATTERN.search(next_line):
                entry["year"] = next_line
                i += 2
            else:
                entry["institution"] = next_line
                if i + 2 < len(lines) and YEAR_PATTERN.search(lines[i + 2]):
                    entry["year"] = lines[i + 2]
                    i += 3
                else:
                    i += 2
        else:
            i += 1
        entries.append(entry)

    return entries


def _parse_certifications(text: str) -> list[str]:
    """Parse certifications as a simple list (one per line or comma-separated)."""
    if not text:
        return []
    certs = []
    for line in text.split("\n"):
        stripped = re.sub(r"^[\•\-\*]\s*", "", line.strip())
        if stripped:
            certs.append(stripped)
    return certs


def _parse_projects(text: str) -> list[dict]:
    """
    Parse projects section. Each project typically has a name line
    followed by a description / bullet lines.
    """
    if not text:
        return []

    BULLET_PATTERN = re.compile(r"^[\•\-\*]\s+")
    entries = []
    lines = [l for l in text.split("\n") if l.strip()]
    current_project = None

    for line in lines:
        stripped = line.strip()
        if BULLET_PATTERN.match(stripped):
            desc = BULLET_PATTERN.sub("", stripped).strip()
            if current_project:
                current_project["description"] += " " + desc
            else:
                current_project = {"name": "", "description": desc}
        else:
            if current_project:
                entries.append(current_project)
            current_project = {"name": stripped, "description": ""}

    if current_project:
        entries.append(current_project)

    return entries


# ---------------------------------------------------------------------------
# Main extractor node
# ---------------------------------------------------------------------------

def extractor_node(state: ResumaticState) -> dict:
    """
    Agent 2 — Resume Extractor node.

    Reads the resume file from state, extracts raw text, splits it into
    sections, and parses each section into the ResumeData schema.
    Writes the result to state["extracted_resume"].
    """
    file_path = state["resume_file_path"]
    print(f"[Extractor] Parsing resume: {file_path}")

    try:
        # Step 1: Extract raw text
        raw_text = _extract_raw_text(file_path)

        # Step 2: Split into sections
        sections = _split_into_sections(raw_text)
        header_text = sections.get("header", raw_text[:500])

        # Step 3: Extract contact info from the header block
        all_lines = raw_text.split("\n")
        name = _extract_name(all_lines)
        email = _extract_email(header_text)
        phone = _extract_phone(header_text)
        linkedin = _extract_linkedin(raw_text)

        # Step 4: Parse each section
        summary = sections.get("summary", "").strip()
        skills = _parse_skills(sections.get("skills", ""))
        experience = _parse_experience(sections.get("experience", ""))
        education = _parse_education(sections.get("education", ""))
        certifications = _parse_certifications(sections.get("certifications", ""))
        projects = _parse_projects(sections.get("projects", ""))

        extracted_resume = {
            "name": name,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "certifications": certifications,
            "projects": projects,
        }

        print(f"[Extractor] Extraction complete. Found {len(experience)} experience entries, "
              f"{len(skills)} skills, {len(education)} education entries.")

        return {"extracted_resume": extracted_resume}

    except Exception as exc:
        print(f"[Extractor] ERROR: {exc}")
        return {"error": f"Extractor failed: {str(exc)}"}
