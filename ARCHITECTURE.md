# Forma Architecture & Systems Design

Forma is an intelligent, reliable, secure, RAG-powered personal AI assistant built for a single private user. It combines multi-model API orchestration with long-term memory, hybrid semantic document retrieval, safe personal tooling, and agentic workflows—all without expensive infrastructure or GPU requirements.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Forma Web UI (React + TS)                │
│  - Calm, spacious green design system                       │
│  - Memory category pills & JSON export/import               │
│  - Agent mode toggle & collapsible step inspection          │
│  - Streaming token rendering & source disclosures           │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / SSE (EventSource)
┌──────────────────────────────▼──────────────────────────────┐
│                  FastAPI Backend (Python 3.11+)              │
│  ┌───────────────────────────┬───────────────────────────┐  │
│  │   Intelligent Routing     │  Provider Cooldown Mgr    │  │
│  │   - Task classification   │  - 429/5xx tracking       │  │
│  │   - Scoring & fallback    │  - Exponential backoff    │  │
│  ├───────────────────────────┼───────────────────────────┤  │
│  │   Long-Term Memory Engine │  Safe Personal Tools      │  │
│  │   - Profile, Project,     │  - AST Python sandbox     │  │
│  │     Episodic, Semantic    │  - GitHub inspector       │  │
│  │   - Credential filtering  │  - Structured CSV/JSON    │  │
│  ├───────────────────────────┼───────────────────────────┤  │
│  │   Hybrid RAG Engine       │  Agentic Orchestrator     │  │
│  │   - Semantic chunking     │  - Multi-step ReAct loop  │  │
│  │   - FTS5 BM25 + Dense Sim │  - Step budget (max 6)    │  │
│  │   - Reciprocal Rank Fusion│  - Tool dispatch & audit  │  │
│  └───────────────────────────┴───────────────────────────┘  │
│                               │                             │
│                  SQLite WAL Database                        │
│   (conversations, messages, memories, document_chunks,      │
│    document_chunks_fts, tool_executions)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### Intelligent Model Routing & Provider Cooldown
- **Task Classification**: Evaluates incoming queries across reasoning, math, coding, creative writing, document analysis, research, and general dialogue.
- **Provider Cooldown Manager**: Tracks rate limits (HTTP 429), authentication failures (401), and upstream server errors (5xx) with exponential cooldown backoffs (30s base, up to 10 min).
- **Graceful Fallback**: Automatically shifts to secondary and tertiary providers when a model fails or quota is exhausted, streaming a `shift` event to the client while preserving conversation context.

### Long-Term Memory Engine
- **Categorization**: Stored memories are categorized into `profile`, `project`, `episodic`, `semantic`, and `conversation`.
- **Privacy & Credential Protection**: Scans potential memories for API keys, tokens, or private secrets and prevents storage.
- **Portability**: Endpoints `GET /api/personalization/export` and `POST /api/personalization/import` allow seamless JSON backup and restoration. Full workspace exports are available at `GET /api/backup`.

### Hybrid RAG System
- **Semantic Document Chunker**: Chunks uploaded documents (PDF, DOCX, TXT, CSV, Code) into 1,000-character windows with 150-character overlap while preserving line numbers and page markers.
- **CPU-Friendly Dense Lexical Vectors**: Generates 128-dimensional dense lexical vectors using deterministic token and character n-gram hashing and term frequency pooling with zero GPU or heavy torch dependencies.
- **Hybrid Search**: Combines SQLite FTS5 BM25 keyword search with dense cosine vector similarity using Reciprocal Rank Fusion (RRF; $k=60$).
- **Strict Evidence Boundaries**: Injects context into prompts using `<retrieved_evidence>` boundary tags to prevent context bleeding and prompt injection.

### Personal AI Tools & Sandboxing
- **In-Process AST-Restricted Python Sandbox**: Executes code in-process with strict AST syntax verification (blocking system-level imports and dangerous builtins), capturing standard output, and enforcing timeout bounds. Permits only safe mathematical and data utilities (`math`, `statistics`, `json`, `re`, `datetime`, `collections`, `itertools`).
- **GitHub Repository Inspector**: Inspects public GitHub repositories (`/repos/{owner}/{repo}`) using unauthenticated or authenticated GitHub API requests, retrieving directory trees and README contents safely.
- **Structured Data Processor**: Parses, cleans, and generates summary statistics for CSV and JSON datasets.
- **Audit Logging**: Every tool execution is recorded in the `tool_executions` SQLite table with conversation ID, input parameters, execution time, and output summary.

### Agentic Multi-Step Workflow
- When Agent Mode is active, Forma runs an autonomous multi-step reasoning loop (budgeted at a maximum of 6 steps).
- The agent reasons about required actions, dispatches sandboxed tool calls, inspects intermediate outputs, and produces a final consolidated response.
- Steps and tool actions stream live to the client as `agent_step` and `agent_action` events, rendered in an expandable disclosure in the chat UI.
