# Resumatic 🎯

A multi-agent resume tailoring system powered by **LangGraph** and **FastAPI**, featuring an intuitive modern web frontend with drag-and-drop resume import.

Upload your existing resume (PDF or DOCX) and a target job description — the AI pipeline extracts your resume content, tailors it to the job, and returns a professionally formatted PDF resume.

---

## Architecture

Resumatic uses a **Supervisor-Worker** multi-agent pattern built on LangGraph, with a
**feedback loop** on the Enhancer stage. The Enhancement Critic validates each output
and loops back with written corrections — up to 3 times — before advancing to PDF generation.

```mermaid
flowchart TD
    UI["🌐 Web Frontend\ndrag-and-drop UI"]
    API["⚡ FastAPI REST API\nPOST /tailor-resume"]
    A1["🧠 Agent 1: Orchestrator\nLLM — validates inputs, routes steps"]
    A2["📄 Agent 2: Extractor\nno LLM — regex PDF/DOCX parser"]
    A3["✍️ Agent 3: Enhancer\nLLM — rewrites resume for the job"]
    CRITIC["🔍 Enhancement Critic\nLLM — validates company names,\nkeyword alignment & bullet quality"]
    A4["🖨️ Agent 4: PDF Generator\nno LLM — renders final PDF"]
    OUT["📎 tailored_resume.pdf"]

    UI -->|"multipart/form-data"| API
    API --> A1
    A1 -->|"extract"| A2
    A2 -->|"done"| A1
    A1 -->|"enhance"| A3
    A3 --> CRITIC
    CRITIC -->|"PASS ✅\nor retries exhausted"| A1
    CRITIC -->|"FAIL ❌\niteration < 3"| A3
    A1 -->|"generate"| A4
    A4 -->|"done"| A1
    A1 -->|"done"| OUT
    API -->|"application/pdf"| UI
```

### The Enhancer Feedback Loop

The **Enhancement Critic** sits between the Enhancer and the Orchestrator and runs two layers of checks:

| Check | Method | What it catches |
|---|---|---|
| **Company name integrity** | Pure Python (no LLM cost) | Company names replaced with role descriptions instead of exact names |
| **Experience entry count** | Pure Python (no LLM cost) | Jobs dropped or merged by the Enhancer |
| **Keyword alignment & bullet quality** | LLM (`CRITIC_MODEL`) | Weak bullets, missing job-description keywords |

If the critic fails, it writes specific feedback back into the Enhancer's prompt for the retry. After **3 iterations** the best available output is forwarded regardless.

### The Five Agents

| Agent | Role | Uses LLM? |
|---|---|---|
| **Agent 1 — Orchestrator** | Supervisor — validates inputs, routes between workers, handles errors | ✅ Yes |
| **Agent 2 — Extractor** | Parses PDF/DOCX resume into structured data (regex + heuristics) | ❌ No |
| **Agent 3 — Enhancer** | Rewrites resume content to match the job description | ✅ Yes |
| **Enhancement Critic** | Validates Enhancer output; loops back with written critique on failure | ✅ Yes (cheap model) |
| **Agent 4 — PDF Generator** | Renders the enhanced content as a clean PDF | ❌ No |

---

# Resumatic Component Dependencies

This diagram illustrates the dependencies between all `.py` files in the Resumatic project. It focuses on internal module imports.

```mermaid
graph TD
    %% Define nodes
    Main["main.py"]
    Graph["graph.py"]
    State["state.py"]
    LLMFactory["llm_factory.py"]
    AuditLogger["audit_logger.py"]

    subgraph Agents Module
        AgentsInit["agents/__init__.py"]
        Orchestrator["agents/orchestrator.py"]
        Extractor["agents/extractor.py"]
        Enhancer["agents/enhancer.py"]
        Critic["agents/critic.py"]
        PDFGen["agents/pdf_generator.py"]
    end

    %% Top-level wiring
    Main --> Graph

    Graph --> AgentsInit
    Graph --> State

    %% __init__ re-exports all agent nodes
    AgentsInit --> Orchestrator
    AgentsInit --> Extractor
    AgentsInit --> Enhancer
    AgentsInit --> Critic
    AgentsInit --> PDFGen

    %% Per-agent dependencies
    Orchestrator --> LLMFactory
    Orchestrator --> State
    Orchestrator --> AuditLogger

    Extractor --> State
    Extractor --> AuditLogger

    Enhancer --> LLMFactory
    Enhancer --> State
    Enhancer --> AuditLogger

    Critic --> LLMFactory
    Critic --> State
    Critic --> AuditLogger

    PDFGen --> State
    PDFGen --> AuditLogger
```


## Quickstart

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd resumatic
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your OpenRouter API key (https://openrouter.ai/keys):
#   OPENROUTER_API_KEY=sk-or-v1-...
# Optionally choose models per agent (defaults work out of the box):
#   ENHANCER_MODEL=anthropic/claude-3.5-sonnet
```

### 3. Start Frontend & Backend

#### Method A: Using the Startup Script (`start.sh`)

The included `start.sh` script automatically activates the virtual environment, checks configuration, and launches the services.

```bash
chmod +x start.sh
./start.sh
```

By default, this launches:
- **Frontend Web UI**: [http://localhost:3000](http://localhost:3000) (and [http://localhost:8000](http://localhost:8000))
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

Press `Ctrl+C` at any time to cleanly stop both services.

**Script flags:**
```bash
./start.sh              # Default: runs backend (:8000) & frontend (:3000)
./start.sh --unified    # Unified mode: FastAPI serves both API & frontend (:8000)
./start.sh --backend    # Runs backend API only (:8000)
./start.sh --frontend   # Runs frontend web server only (:3000)
./start.sh --help       # Display help menu
```

---

#### Method B: Manual Commands

##### 1. Unified Mode (FastAPI serves Backend + Frontend)
Since FastAPI mounts the `frontend/` directory, you can run both frontend and backend on a single port:

```bash
uvicorn main:app --reload --port 8000
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

##### 2. Separate Frontend and Backend
If you prefer running frontend and backend in isolated terminal processes:

- **Terminal 1 (Backend API):**
  ```bash
  uvicorn main:app --reload --port 8000
  ```

- **Terminal 2 (Frontend Static Server):**
  ```bash
  python3 -m http.server 3000 --directory frontend
  ```
  Then open **[http://localhost:3000](http://localhost:3000)** in your browser. (The frontend automatically routes API requests to `http://localhost:8000`).

---

## Web Frontend Features

The frontend is completely isolated in the `frontend/` directory with zero build dependencies (vanilla HTML5, CSS3, and modern ES6 JavaScript):

- **Drag-and-Drop Resume Upload**: Drag `.pdf` or `.docx` files directly into the drop zone with instant visual feedback and active state styling.
- **Click-to-Browse**: Standard accessible file picker fallback.
- **Client-Side Validation**: Immediate validation for file format and file size limits (max 10 MB).
- **File Preview & Remove**: Displays filename, formatted size, and quick removal.
- **Job Description Input**: Expandable textarea with live character counter.
- **Multi-Stage Progress Indicator**: Visual step-by-step pipeline status (*Extracting* → *Enhancing* → *Generating PDF*).
- **Automatic PDF Download**: Automatically triggers download of the tailored PDF upon completion, with a "Download Again" option.
- **Error Feedback**: User-friendly alerts and "Try Again" recovery.
- **Responsive Layout**: Designed for mobile, tablet, and desktop screens.

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
├── start.sh              # Startup script for frontend and backend
├── main.py               # FastAPI app — endpoints, CORS, static frontend mount
├── graph.py              # LangGraph StateGraph wiring (incl. critic loop)
├── state.py              # Shared state schema (ResumaticState TypedDict)
├── llm_factory.py        # Shared LLM factory — OpenRouter API, per-agent model config
├── audit_logger.py       # Structured audit logging for every agent input/output
├── frontend/             # Dedicated isolated frontend directory
│   ├── index.html        # Single-page web interface (semantic HTML)
│   ├── css/
│   │   └── styles.css    # Responsive styling, animations & theme
│   └── js/
│       └── app.js        # Drag-and-drop, API integration & state management
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py   # Agent 1: Supervisor (LLM)
│   ├── extractor.py      # Agent 2: Resume parser (no LLM)
│   ├── enhancer.py       # Agent 3: Content tailor (LLM)
│   ├── critic.py         # Enhancement Critic: quality gate with feedback loop (LLM)
│   └── pdf_generator.py  # Agent 4: PDF builder (no LLM)
├── audit/                # Per-run structured logs (gitignored)
├── sample/
│   └── sample_jd.txt     # Sample job description for testing
├── output/               # Generated PDFs (gitignored)
├── uploads/              # Temp upload files (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## LLM Provider

All LLM calls route through **[OpenRouter](https://openrouter.ai)**, which provides a
unified OpenAI-compatible API for hundreds of models. Set your key and per-agent models
in `.env`:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...

# Per-agent model selection (see https://openrouter.ai/models for all slugs)
ORCHESTRATOR_MODEL=meta-llama/llama-3.1-8b-instruct:free   # Fast/free — only writes short status lines
ENHANCER_MODEL=anthropic/claude-3.5-haiku                   # High-quality writing model
CRITIC_MODEL=meta-llama/llama-3.1-8b-instruct:free          # Fast/cheap — critic output is short
```

> **Tip:** Use a high-quality model (e.g. `anthropic/claude-3.5-sonnet` or `openai/gpt-4o`)
> for `ENHANCER_MODEL` and a cheap/fast model for `CRITIC_MODEL` and `ORCHESTRATOR_MODEL`
> to get the best quality-to-cost ratio.

---

## Key LangChain / LangGraph Concepts Demonstrated

| Concept | Where |
|---|---|
| Supervisor Pattern | `orchestrator.py` — delegates to workers, advances pipeline steps |
| Shared State | `state.py` — single `ResumaticState` TypedDict passed across all nodes |
| Heterogeneous Agents | Agents 1, 3 & Critic use LLM; Agents 2 & 4 do not |
| Conditional Routing | `graph.py` — `add_conditional_edges()` for both orchestrator and critic |
| **Loop Engineering** | `graph.py` — Enhancer ↔ Critic feedback loop, max 3 iterations |
| **Critic Pattern** | `critic.py` — validates output, injects written feedback for retry |
| Structured Output | `enhancer.py` — `llm.with_structured_output()` |
| API-First Design | `main.py` — FastAPI decouples backend from frontend |
