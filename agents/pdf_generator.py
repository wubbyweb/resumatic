"""
agents/pdf_generator.py
-----------------------
Agent 4: PDF Generator

Role:  Convert the enhanced resume content into a clean, professional PDF file.
LLM:   NO — purely programmatic layout using FPDF2.

Responsibilities:
  1. Read the enhanced_resume dict from state.
  2. Build a PDF document section by section using FPDF2.
  3. Save the PDF to ./output/<uuid>_tailored_resume.pdf.
  4. Write the output path to state["output_pdf_path"].

PDF Layout:
  - Header: Name (large, bold) + contact info (email | phone | LinkedIn)
  - Section separator lines + bold uppercase section titles
  - Sections: Summary → Skills → Experience → Education → Certifications → Projects
  - Font: Helvetica (built-in, no installation required)
  - Page margins: 15mm left/right, 15mm top

Note: Uses FPDF2 v2.5+ XPos/YPos API (replaces deprecated ln=True/False).
"""

import os
from uuid import uuid4

from fpdf import FPDF, XPos, YPos

from state import ResumaticState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
PAGE_WIDTH = 210          # A4 width in mm
MARGIN = 15               # Left/right margin in mm
CW = PAGE_WIDTH - 2 * MARGIN   # Usable content width

# Colours (RGB)
COLOR_DARK_GRAY = (50, 50, 50)
COLOR_MID_GRAY  = (100, 100, 100)
COLOR_RULE      = (180, 180, 180)
COLOR_ACCENT    = (30, 80, 160)   # Deep blue for name and section titles


# ---------------------------------------------------------------------------
# Custom FPDF subclass
# ---------------------------------------------------------------------------

class ResumePDF(FPDF):
    """FPDF2 subclass with helper methods for clean resume layout."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(MARGIN, 15, MARGIN)
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        self.set_font("Helvetica", size=10)

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------

    def render_header(self, resume: dict):
        """Name (centred, large) + single contact info line."""
        name    = resume.get("name", "")
        email   = resume.get("email", "")
        phone   = resume.get("phone", "")
        linkedin = resume.get("linkedin", "")

        # Name — large bold centred
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(CW, 10, name.upper(), align="C",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Contact line
        contact_parts = [p for p in [email, phone, linkedin] if p]
        self.set_font("Helvetica", size=9)
        self.set_text_color(*COLOR_MID_GRAY)
        self.cell(CW, 5, "  |  ".join(contact_parts), align="C",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    # -------------------------------------------------------------------------
    # Section separator
    # -------------------------------------------------------------------------

    def render_section_title(self, title: str):
        """Horizontal rule + bold uppercase section title."""
        self.set_draw_color(*COLOR_RULE)
        self.set_line_width(0.3)
        self.line(MARGIN, self.get_y(), PAGE_WIDTH - MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(CW, 5, title.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)
        self.set_text_color(*COLOR_DARK_GRAY)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------

    def render_summary(self, resume: dict):
        summary = resume.get("summary", "").strip()
        if not summary:
            return
        self.render_section_title("Professional Summary")
        self.set_font("Helvetica", size=9)
        self.set_text_color(*COLOR_DARK_GRAY)
        self.multi_cell(CW, 5, summary, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    # -------------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------------

    def render_skills(self, resume: dict):
        skills = resume.get("skills", [])
        if not skills:
            return
        self.render_section_title("Skills")
        self.set_font("Helvetica", size=9)
        self.set_text_color(*COLOR_DARK_GRAY)
        self.multi_cell(CW, 5, "  -  ".join(skills),
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    # -------------------------------------------------------------------------
    # Experience
    # -------------------------------------------------------------------------

    def render_experience(self, resume: dict):
        experience = resume.get("experience", [])
        if not experience:
            return
        self.render_section_title("Experience")

        for entry in experience:
            title    = entry.get("title", "")
            company  = entry.get("company", "")
            duration = entry.get("duration", "")
            bullets  = entry.get("bullets", [])

            # Title + company (bold), duration right-aligned on same row
            title_company = title + (f"  -  {company}" if company else "")
            dur_width  = 45 if duration else 0
            title_width = CW - dur_width

            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*COLOR_DARK_GRAY)
            self.cell(title_width, 5, title_company,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)

            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*COLOR_MID_GRAY)
            self.cell(dur_width, 5, duration, align="R",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Bullet points
            self.set_font("Helvetica", size=9)
            self.set_text_color(*COLOR_DARK_GRAY)
            for b in bullets:
                self.cell(5, 5, "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
                self.multi_cell(CW - 5, 5, b,
                                new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            self.ln(2)

        self.ln(1)

    # -------------------------------------------------------------------------
    # Education
    # -------------------------------------------------------------------------

    def render_education(self, resume: dict):
        education = resume.get("education", [])
        if not education:
            return
        self.render_section_title("Education")

        for entry in education:
            degree      = entry.get("degree", "")
            institution = entry.get("institution", "")
            year        = entry.get("year", "")

            degree_text = degree + (f"  -  {institution}" if institution else "")
            year_width  = 35 if year else 0

            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*COLOR_DARK_GRAY)
            self.cell(CW - year_width, 5, degree_text,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)

            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*COLOR_MID_GRAY)
            self.cell(year_width, 5, year, align="R",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(3)

    # -------------------------------------------------------------------------
    # Certifications
    # -------------------------------------------------------------------------

    def render_certifications(self, resume: dict):
        certs = resume.get("certifications", [])
        if not certs:
            return
        self.render_section_title("Certifications")
        self.set_font("Helvetica", size=9)
        self.set_text_color(*COLOR_DARK_GRAY)
        for cert in certs:
            self.cell(5, 5, "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.cell(CW - 5, 5, cert, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    def render_projects(self, resume: dict):
        projects = resume.get("projects", [])
        if not projects:
            return
        self.render_section_title("Projects")

        for project in projects:
            name = project.get("name", "")
            desc = project.get("description", "")

            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*COLOR_DARK_GRAY)
            self.cell(CW, 5, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            if desc:
                self.set_font("Helvetica", size=9)
                self.multi_cell(CW, 5, desc,
                                new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)


# ---------------------------------------------------------------------------
# PDF Generator node
# ---------------------------------------------------------------------------

def pdf_generator_node(state: ResumaticState) -> dict:
    """
    Agent 4 — PDF Generator node.

    Reads enhanced_resume from state, builds a PDF using FPDF2,
    saves it to ./output/<uuid>_tailored_resume.pdf, and writes
    the output path to state["output_pdf_path"].
    """
    print("[PDF Generator] Building PDF...")

    enhanced_resume = state.get("enhanced_resume")
    if not enhanced_resume:
        return {"error": "PDF Generator received empty enhanced_resume."}

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        output_filename = f"{uuid4()}_tailored_resume.pdf"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        pdf = ResumePDF()
        pdf.render_header(enhanced_resume)
        pdf.render_summary(enhanced_resume)
        pdf.render_skills(enhanced_resume)
        pdf.render_experience(enhanced_resume)
        pdf.render_education(enhanced_resume)
        pdf.render_certifications(enhanced_resume)
        pdf.render_projects(enhanced_resume)

        pdf.output(output_path)

        print(f"[PDF Generator] PDF saved to: {output_path}")
        return {"output_pdf_path": output_path}

    except Exception as exc:
        print(f"[PDF Generator] ERROR: {exc}")
        return {"error": f"PDF Generator failed: {exc!s}"}
