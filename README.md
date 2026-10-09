# Forma AI

<p align="center">
  <strong>Think it. Shape it.</strong><br>
  A college project with multi-provider chat, document retrieval, saved preferences, and optional Agent Mode.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/SQLite_FTS5-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License" />
</p>

---

## Overview

**Forma** is an AI chatbot built with React and FastAPI. It supports cloud providers such as Groq, Gemini and OpenAI, or local models through Ollama. It includes conversation history, document retrieval, saved memories and optional multi-step tools.

Cloud providers receive the prompts and context sent to them, which can include messages, relevant document extracts and saved preferences. Local Ollama can keep model inference on your own machine, but web search and GitHub tools still make external requests. Hosting and provider usage may have costs or limits.

---

## Key Capabilities

### 🧠 Intelligent Model Routing & Provider Auto-Failover
- **Independent Request Classification**: Evaluates every incoming prompt and identifies task intent across reasoning, mathematics, coding, creative writing, research, document analysis, and general dialogue.
- **`ProviderCooldownManager`**: Intelligently monitors API rate limits (HTTP 429), authentication issues (401), and upstream outages (5xx) with exponential backoff cooldowns (30s base up to 10 minutes).
- **Zero-Disruption Fallback**: Automatically and transparently switches to compatible secondary and tertiary models without losing conversation context, streaming live shift notifications to the UI.

### 📚 CPU-Friendly Hybrid RAG Engine
- **Semantic Document Chunking**: Ingests PDFs, DOCX files, codebases, CSVs, and plain text with 1,000-character semantic windows and 150-character overlaps, preserving line numbers and page markers.
- **Lexical BM25 + Dense Lexical Vector Hybrid Search**: Combines SQLite FTS5 full-text search with 128-dimensional dense lexical vectors using token and character n-gram hashing and Reciprocal Rank Fusion (RRF; $k=60$)—delivering fast, high-precision retrieval with zero GPU or PyTorch overhead.
- **Strict Evidence Boundaries**: Injects context into prompts using isolated `<retrieved_evidence>` boundaries to distinguish retrieved text from instructions. These delimiters do not guarantee protection against hallucinations or prompt injection.

### 💾 Categorized Long-Term Memory Engine
- **Categorized memory records**: Organizes learned knowledge into distinct categories: `profile` (personal preferences), `project` (active repositories, stacks, goals), `episodic` (past decisions, milestones), and `semantic` (domain facts).
- **Credential & Secret Protection**: Actively detects, redacts, and rejects API keys, passwords, and sensitive tokens from being committed into long-term memory.
- **Full Portability**: Easily view, filter by category, edit, export, or import memories as standard JSON.

### 🤖 Agent Mode & Tools
- **Multi-Step ReAct Agent**: Solves complex questions using an iterative ReAct reasoning loop (budgeted up to 6 steps) with real-time thought and action streaming.
- **Python execution disabled**: Arbitrary Python code is not executed. The previous in-process runner was removed because it did not provide a secure boundary or enforceable timeout. Re-enabling code execution requires a separate isolated service with resource limits.
- **GitHub Repository Inspector**: Safely inspects public repositories, directory trees, commit structures, and README files.
- **Structured Data Processor**: Parses, cleans, and computes summary statistics for CSV and JSON datasets.
- **Tool Audit Logging**: Every tool execution is captured in SQLite with execution duration, arguments, and outputs.

### 🌐 Real-Time Web Search & Fact Verification
- **Multi-Tier Search Fallback**: Seamlessly queries configured API providers (**Tavily**, **Brave**) with graceful fallback to **DuckDuckGo**.
- **Temporal & Person Verification**: Automatically identifies time-sensitive queries ("latest", "today", "who is") and queries current roles and recent developments separately.
- **In-Memory TTL Caching**: 10-minute cache with URL deduplication to minimize network overhead and respect API rate limits.

### 🎨 The Forma Design System
- **Clean & Calm Aesthetic**: Thoughtfully crafted with comfortable margins, fluid typography, dark/light themes, and custom accent colors.
- **Unified Model Selector**: Real-time capability indicators (Vision, Reasoning, Fast, Local Ollama, Image Generation) accessible from the sidebar and header.
- **Collapsible Agent Disclosures**: Expandable step-by-step progress cards showing agent thoughts and tool outputs without cluttering the chat view.
- **Responsive Workspace**: Seamless experience across mobile drawers (360px+), tablets, laptops, and ultra-wide desktop monitors (1920px+).

---

## Architecture

Forma is built with a lightweight, high-performance architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Forma Web UI (React + TS)                │
│  - Clean, responsive desktop & mobile workspace             │
│  - Category-filtered memory manager & JSON export/import    │
│  - Agent Mode toggle with live reasoning disclosures        │
│  - Unified model selector & multi-source web citations      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / SSE (EventSource)
┌──────────────────────────────▼──────────────────────────────┐
│                  FastAPI Backend (Python 3.11+)              │
│  ┌───────────────────────────┬───────────────────────────┐  │
│  │   Intelligent Routing     │  Provider Cooldown Mgr    │  │
│  │   - Task classification   │  - 429/5xx exponential    │  │
│  │   - Capability matching   │  - Transparent failover   │  │
│  ├───────────────────────────┼───────────────────────────┤  │
│  │   Long-Term Memory Engine │  Safe Personal Tools      │  │
│  │   - Profile, Project,     │  - Python disabled        │  │
│  │     Episodic, Semantic    │  - GitHub repo inspector  │  │
│  │   - Credential filtering  │  - CSV / JSON processor   │  │
│  ├───────────────────────────┼───────────────────────────┤  │
│  │   Hybrid RAG Engine       │  Autonomous Agent         │  │
│  │   - Semantic chunking     │  - Multi-step ReAct loop  │  │
│  │   - FTS5 BM25 + Dense Sim │  - Step budget & stream   │  │
│  │   - Reciprocal Rank Fusion│  - Audit log recorder     │  │
│  └───────────────────────────┴───────────────────────────┘  │
│                               │                             │
│                  SQLite WAL Database                        │
│   (conversations, messages, memories, document_chunks,      │
│    document_chunks_fts, tool_executions)                    │
└─────────────────────────────────────────────────────────────┘
```

For detailed component documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 20+**
- (Optional) [Ollama](https://ollama.ai) for local offline models

### 1. Clone & Set Up the Backend

```bash
git clone https://github.com/Tishal68/Forma-chatbot.git
cd Forma-chatbot

# Set up Python virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r backend/requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` and add your preferred provider keys:

```ini
# At least one model provider:
GROQ_API_KEY=gsk_your_groq_key
GEMINI_API_KEY=AIza_your_gemini_key
OPENAI_API_KEY=sk_your_openai_key

# Or run completely locally with Ollama (no API keys needed!):
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Optional: Enhanced Web Search APIs
TAVILY_API_KEY=tvly_your_tavily_key
BRAVE_API_KEY=BSAx_your_brave_key

# GitHub inspection supports public repositories only and never uses server tokens.
```

### 3. Launch Backend & Frontend

Start the backend:
```bash
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In a new terminal, start the frontend:
```bash
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173** in your browser.

---

## Verification & Testing

Forma maintains an extensive automated test suite covering routing, memory, RAG, disabled code execution, and UI responsiveness:

```bash
# Run all backend unit & integration tests (154+ tests)
python -m pytest -q

# Run frontend build & Playwright responsive tests
cd frontend
npm run build
npx playwright install chromium
npm run test:ui
```

---

## Production Deployment

Forma is ready for containerized deployment or hosting on platforms like **Render**, **Railway**, or **Docker**:

```bash
# Build and run the unified Docker container
docker build -t forma-chat .
docker run -p 8000:8000 -v forma-data:/app/data --env-file .env forma-chat
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guides, volume persistence, and reverse proxy configurations.

---

## Privacy & Security

- **Session separation**: Conversations and preferences are associated with a visitor session. The server operator controls the database; this is not end-to-end encryption.
- **No Telemetry**: Zero analytics, external trackers, or third-party tracking cookies.
- **Code execution**: Disabled server-side and unavailable to Agent Mode.
- **Credential Protection**: Automatic credential scanning prevents sensitive keys or tokens from being saved in memory.
- **JSON export**: `GET /api/backup` exports conversations, messages, personalization and attachment metadata. It does not include attachment file contents.

---

## License

Distributed under the [MIT License](LICENSE).
