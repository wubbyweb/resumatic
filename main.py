"""
main.py
-------
Resumatic — FastAPI REST API

Exposes the multi-agent resume tailoring pipeline as an HTTP API.
Any frontend (web app, mobile app, CLI) can POST a resume file and a
job description, and receive a tailored PDF resume as the response.

Endpoints:
  POST /tailor-resume   — main pipeline endpoint
  GET  /health          — health check

Usage:
  uvicorn main:app --reload --port 8000

API docs (auto-generated Swagger UI):
  http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
load_dotenv()

# Import the compiled LangGraph (built once at startup)
from graph import resumatic_graph

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "output")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _ensure_directories():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create required directories and validate configuration on startup."""
    _ensure_directories()
    _validate_api_key()
    print("✅ Resumatic API started. Docs at http://localhost:8000/docs")
    yield
    print("🛑 Resumatic API shutting down.")


app = FastAPI(
    title="Resumatic API",
    description=(
        "Multi-agent resume tailoring system powered by LangGraph.\n\n"
        "Upload your resume (PDF or DOCX) and a job description, "
        "and receive a tailored PDF resume as a download."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS — allow all origins during development
# ---------------------------------------------------------------------------
# In production, replace allow_origins=["*"] with your frontend's domain.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Simple health check.
    Returns 200 OK when the API is running.
    """
    return {"status": "ok", "service": "Resumatic API"}


@app.post(
    "/tailor-resume",
    tags=["Resume"],
    summary="Tailor a resume to a job description",
    response_description="A tailored PDF resume file",
)
async def tailor_resume(
    resume: UploadFile = File(
        ...,
        description="The candidate's existing resume file (PDF or DOCX).",
    ),
    job_description: str = Form(
        ...,
        description="The full text of the target job description.",
    ),
):
    """
    Run the multi-agent pipeline:

    1. **Extractor** (no LLM) — parses the uploaded resume into structured data.
    2. **Enhancer** (LLM) — rewrites and tailors the content to match the job description.
    3. **PDF Generator** (no LLM) — renders a clean, professional PDF resume.

    Returns the tailored resume as a downloadable PDF.
    """
    # --- Input validation ---
    if not resume.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = os.path.splitext(resume.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Please upload a PDF or DOCX file.",
        )

    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description cannot be empty.",
        )

    # --- Save uploaded file to a unique temp path ---
    upload_filename = f"{uuid4()}{ext}"
    upload_path = os.path.join(UPLOADS_DIR, upload_filename)

    try:
        with open(upload_path, "wb") as f:
            content = await resume.read()
            f.write(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    # --- Invoke the LangGraph multi-agent pipeline ---
    try:
        print(f"\n{'='*60}")
        print(f"[API] New request — file: {resume.filename}")
        print(f"[API] Job description length: {len(job_description)} chars")
        print(f"{'='*60}")

        initial_state = {
            "resume_file_path": upload_path,
            "job_description": job_description,
            "extracted_resume": None,
            "enhanced_resume": None,
            "output_pdf_path": "",
            "messages": [],
            "current_step": "",   # Orchestrator sets this on first call
            "error": None,
        }

        result = resumatic_graph.invoke(initial_state)

    except Exception as exc:
        # Clean up upload on pipeline failure
        _cleanup_file(upload_path)
        if _is_auth_error(exc):
            raise HTTPException(
                status_code=401,
                detail=(
                    "OpenRouter API key is invalid or expired (401 User not found). "
                    "Please update OPENROUTER_API_KEY in your .env file. "
                    "Get a valid key at https://openrouter.ai/keys"
                ),
            )
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc!s}")

    # --- Check for pipeline errors ---
    if result.get("error"):
        _cleanup_file(upload_path)
        error_msg = result["error"]
        print(f"[API] Pipeline returned error: {error_msg}")
        status = 401 if _is_auth_error(Exception(error_msg)) else 500
        raise HTTPException(status_code=status, detail=error_msg)

    pdf_path = result.get("output_pdf_path", "")
    if not pdf_path or not os.path.exists(pdf_path):
        _cleanup_file(upload_path)
        raise HTTPException(status_code=500, detail="PDF was not generated. Check server logs.")

    # --- Clean up the uploaded temp file ---
    _cleanup_file(upload_path)

    print(f"[API] Returning PDF: {pdf_path}")

    # --- Return the PDF as a file download ---
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="tailored_resume.pdf",
        headers={"Content-Disposition": "attachment; filename=tailored_resume.pdf"},
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _cleanup_file(path: str):
    """Silently delete a file if it exists."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _validate_api_key():
    """
    Warn loudly at startup if OPENROUTER_API_KEY is missing.
    A missing or invalid key causes every pipeline request to fail with 401,
    which surfaces as a 500 Internal Server Error to the client.
    """
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        print(
            "\n⚠️  WARNING: OPENROUTER_API_KEY is not set in your .env file!\n"
            "   All /tailor-resume requests will fail.\n"
            "   Get a free key at: https://openrouter.ai/keys\n"
            "   Then add to .env:  OPENROUTER_API_KEY=sk-or-v1-...\n"
        )
    else:
        print(f"🔑 OpenRouter API key loaded (ends: ...{key[-6:]})")


def _is_auth_error(exc: Exception) -> bool:
    """Return True if the exception indicates an invalid/expired API key."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in [
        "401", "user not found", "authentication", "invalid api key",
        "openai authentication", "authenticationerror",
    ])


# ---------------------------------------------------------------------------
# Static frontend — serves the web UI at /
# ---------------------------------------------------------------------------
# Mounted AFTER API routes so /health and /tailor-resume take precedence.
# html=True serves index.html when the root path is requested.

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
