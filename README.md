# Resumatic 🎯

A multi-agent resume tailoring system powered by **LangGraph** and **FastAPI**.

Upload your existing resume (PDF or DOCX) and a target job description — the AI pipeline
extracts your resume content, tailors it to the job, and returns a professionally formatted
PDF resume.

---

## Architecture

```
Frontend (any)
     │
     │  POST /tailor-resume
     │  multipart/form-data
     ▼
┌─────────────────────────────────────────┐
│           FastAPI REST API              │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │    LangGraph StateGraph          │   │
│  │                                  │   │
│  │  Agent 1: Orchestrator (LLM) ◄─┐│   │
│  │      │ extract                  ││   │
│  │      ▼                          ││   │
│  │  Agent 2: Extractor (no LLM)   ─┘│   │
│  │      │ enhance                  ││   │
│  │      ▼                    ◄─────┘│   │
│  │  Agent 3: Enhancer (LLM)  ──────►│   │
│  │      │ generate                  │   │
│  │      ▼                           │   │
│  │  Agent 4: PDF Generator (no LLM) │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
     │
     │  Response: application/pdf
     ▼
tailored_resume.pdf
```

### The Four Agents

| Agent | Role | Uses LLM? |
|---|---|---|
| **Agent 1 — Orchestrator** | Supervisor — validates inputs, routes between workers, handles errors | ✅ Yes |
| **Agent 2 — Extractor** | Parses PDF/DOCX resume into structured data (regex + heuristics) | ❌ No |
| **Agent 3 — Enhancer** | Rewrites resume content to match the job description | ✅ Yes |
| **Agent 4 — PDF Generator** | Renders the enhanced content as a clean PDF | ❌ No |

---

## Quickstart

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd resumatic
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API key:
#   OPENAI_API_KEY=sk-...
#   MODEL_NAME=gpt-4o-mini
```

### 3. Start the API server

```bash
uvicorn main:app --reload --port 8000
```

The API is now running at **http://localhost:8000**.
Interactive Swagger docs: **http://localhost:8000/docs**

---

## API Reference

### `POST /tailor-resume`

| Field | Type | Required | Description |
|---|---|---|---|
| `resume` | File | ✅ | Resume file (PDF or DOCX) |
| `job_description` | string (form) | ✅ | Target job description text |

**Response:** `application/pdf` — the tailored resume as a downloadable file.

#### cURL example

```bash
curl -X POST http://localhost:8000/tailor-resume \
  -F "resume=@./sample/sample_resume.pdf" \
  -F "job_description=$(cat ./sample/sample_jd.txt)" \
  --output tailored_resume.pdf
```

#### JavaScript `fetch` example

```javascript
const formData = new FormData();
formData.append('resume', fileInput.files[0]);
formData.append('job_description', document.getElementById('jd').value);

const response = await fetch('http://localhost:8000/tailor-resume', {
  method: 'POST',
  body: formData,
});

const blob = await response.blob();
const url = URL.createObjectURL(blob);
// Trigger download
const a = document.createElement('a');
a.href = url;
a.download = 'tailored_resume.pdf';
a.click();
```

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"Resumatic API"}
```

---

## Project Structure

```
resumatic/
├── main.py              # FastAPI app — endpoints, CORS, file handling
├── graph.py             # LangGraph StateGraph wiring
├── state.py             # Shared state schema (ResumaticState TypedDict)
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py  # Agent 1: Supervisor (LLM)
│   ├── extractor.py     # Agent 2: Resume parser (no LLM)
│   ├── enhancer.py      # Agent 3: Content tailor (LLM)
│   └── pdf_generator.py # Agent 4: PDF builder (no LLM)
├── sample/
│   └── sample_jd.txt    # Sample job description for testing
├── output/              # Generated PDFs (gitignored)
├── uploads/             # Temp upload files (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## LLM Provider

The system supports **OpenAI** (default) or **Google Gemini**.

Set in `.env`:

```bash
# OpenAI (default)
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini

# OR Google Gemini
GOOGLE_API_KEY=AIza...
MODEL_NAME=gemini-2.0-flash
```

---

## Key LangChain / LangGraph Concepts Demonstrated

| Concept | Where |
|---|---|
| Supervisor Pattern | `orchestrator.py` — delegates to workers |
| Shared State | `state.py` — single `ResumaticState` TypedDict |
| Heterogeneous Agents | Agents 1 & 3 use LLM; Agents 2 & 4 do not |
| Conditional Routing | `graph.py` — `add_conditional_edges()` |
| Structured Output | `enhancer.py` — `llm.with_structured_output()` |
| API-First Design | `main.py` — FastAPI decouples backend from frontend |
