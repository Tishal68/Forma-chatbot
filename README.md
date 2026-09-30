# Forma — local AI workspace

A complete single-user conversational assistant built with React, TypeScript, Vite, FastAPI, Ollama and SQLite. Questions, programming, writing, studying, planning and everyday conversation share the same contextual chat experience.

## Deploy to Render or Railway

See [DEPLOYMENT.md](DEPLOYMENT.md) for the deployment steps. Included: a multi-stage Dockerfile, Render Blueprint, Railway configuration, persistent database path, production password protection and GitHub Actions checks. Hosting requires a reachable Ollama server and a persistent disk/volume. It is one shared workspace, not separate user accounts.

## Included

- Ollama token streaming over POST + Server-Sent Events, with immediate incremental rendering, cancellation, partial-response persistence and actionable errors.
- Independent persistent conversations, derived first-message titles, title/content search, rename, confirmed delete and clear history.
- Conversation context, bounded rolling model-generated summaries and recent verbatim turns. Original messages remain in the database.
- Regenerate the latest answer; edit an earlier user turn and replace later replies.
- Markdown/GFM tables, highlighted code, language labels, copy actions, animated generation state and conditional automatic scrolling.
- Installed-model selector, temperature control, system/light/dark themes, responsive navigation and accessible native settings dialog.
- No account, API key or cloud AI service required. No generated code is executed.

## Prerequisites

- Python 3.11+ and Node.js 20.19+ (or Node 22+ recommended), npm.
- [Ollama](https://ollama.com/download) installed locally. Enough disk/RAM for your chosen model; the example model download is roughly 2 GB.

## Quick start

**Already set up on Windows? Double-click `Launch Forma.cmd`.** It starts the application in the background and opens your browser. If Forma is already running, it reuses that instance. Ollama is started when available. You can right-click the launcher and create a shortcut for convenient access. Closing the browser leaves the local service running, so reopening is fast.

The interface now selects an installed model automatically, restores your last conversation on refresh, and includes a **Quick guide** in the sidebar. Use **Ctrl + K** to find a chat and **Ctrl + Shift + O** to start a new one. On macOS, use Command instead of Ctrl.

From this project directory, create the backend environment:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
ollama pull llama3.2
```

Ollama Desktop normally starts the server. If it is not running, use `ollama serve` in a separate terminal. Do not start a second copy if port 11434 is already occupied.

Start the backend:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to FastAPI; no browser-to-Ollama requests are needed. Select your installed model in the header or Settings.

On macOS/Linux use `python3`, `.venv/bin/python` and `cp .env.example .env` for equivalent commands.

## Production-style local start

```powershell
cd frontend
npm run build
cd ..
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

FastAPI serves the built frontend at **http://127.0.0.1:8000** when `frontend/dist` exists at startup. Restart the backend after the first build. Use a single worker: active-generation ownership is process-local. Production deployments use the password-protected shared workspace described in DEPLOYMENT.md; separate user accounts are not implemented.

## Configuration

Copy `.env.example` to `.env` in the project root. Backend values never enter frontend JavaScript.

- `OLLAMA_BASE_URL`: defaults to `http://localhost:11434`.
- `OLLAMA_MODEL`: default model, example `llama3.2`. UI model selection overrides this per request.
- `DATABASE_PATH`: defaults to `data/chat.db`, relative to the project root.
- `CONTEXT_TOKENS`: model context request, default 8192.
- `OUTPUT_TOKENS`: maximum generated output, default 4096. Raise both context and output for longer answers if your model and hardware support them.
- `GENERATION_TIMEOUT`: per-network-read timeout, default 300 seconds.

The context budget reserves output space. A conservative UTF-8 byte estimate bounds prompts without needing a model-specific tokenizer. Summarization can begin earlier than necessary. Older history is summarized in bounded batches, preserving facts, requirements, decisions and unresolved questions. Extremely long historical turns may be clipped during summarization (marked in the source), and summaries are lossy. The full original text stays in SQLite. Oversized new messages fail visibly rather than silently losing the latest question. Memory updates can delay the first answer token; the UI reports that step immediately.

## Structure

```text
backend/
  app/main.py         REST endpoints, streaming and lifecycle
  app/database.py     SQLite schema and transactions
  app/context.py      system prompt and bounded memory
  tests/test_api.py   integration tests with a controlled Ollama transport
frontend/
  src/main.tsx        application state and interface
  src/components/Message.tsx  memoized Markdown messages
  src/services/api.ts        REST and incremental SSE parser
  src/styles.css     responsive design and theme tokens
data/                automatically created local database
.env.example
README.md
```

## API

- `GET /api/health`: application health.
- `GET /api/models`: installed Ollama models and configured default.
- `GET/POST/DELETE /api/conversations`: list/search, create, clear all.
- `GET/PATCH/DELETE /api/conversations/{id}`: fetch messages, rename, delete.
- `POST /api/chat`: send `conversation_id`, `content`, optional `model`, `temperature`, `regenerate`, `edit_message_id`; returns SSE `start`, `status`, `token`, `error`, `done` events.
- `POST /api/conversations/{id}/stop`: stop an active generation and persist its partial response.
- Interactive API docs: `/docs`.

## Persistence and security

SQLite initializes automatically, enables foreign keys and WAL, and uses parameterized queries. Conversation deletion cascades to messages. User messages are saved before generation; partial assistant content is saved on completion, cancellation or handled failure. An abrupt process kill can lose the in-flight assistant text; startup marks unfinished responses stopped. Back up the database while the app is stopped (or use SQLite's backup API).

Markdown uses React's safe rendering and does not enable arbitrary raw HTML. Cross-origin mutating requests are rejected except configured origins. Bind local development to loopback. Production requires workspace authentication; database encryption at rest depends on your host. Google Fonts is an optional external typography request, with local font fallbacks; no conversation content is sent to it. Remove the stylesheet import for fully offline font loading. Optional remote Ollama bearer credentials remain on the backend.

## Tests

```powershell
.venv\Scripts\python -m pytest backend/tests --import-mode=importlib
cd frontend
npm run build
```

The included `pytest.ini` configures the backend import path. Automated tests use a temporary SQLite database and controlled Ollama transport. Live Ollama and browser test results are recorded in `VERIFICATION.md`. A reusable Playwright browser scenario is also included: with the built app running on port 8000 and `llama3.2:latest` installed, run `npx playwright install chromium`, then `npm run test:e2e -- --timeout=600000` from `frontend`. It creates disposable verification conversations in the running app. The Python lockfile records the tested dependency versions; use `backend/requirements-lock.txt` for exact reproduction.

## Troubleshooting

- **Cannot reach backend:** start uvicorn on port 8000. Use the Vite URL during development or build the frontend before using port 8000.
- **Unable to connect to Ollama:** start Ollama, then check `ollama list` and `http://localhost:11434/api/tags`.
- **No models/model missing:** run `ollama pull <model-name>`, then Settings → Refresh installed models.
- **Slow first response:** model loading and CPU inference take time. Try a smaller model; Stop closes the HTTP generation stream. Cold loading can take longer than warm follow-ups.
- **Timeout:** increase `GENERATION_TIMEOUT` or choose a smaller model. Retry is available on the latest assistant response.
- **Context too large:** shorten the prompt or raise `CONTEXT_TOKENS`, leaving at least 1024 tokens above `OUTPUT_TOKENS` and respecting model/RAM limits.
- **Database failure:** check disk space and write permissions for `data/`; keep the database on a local filesystem.
- **Copy unavailable:** use localhost/loopback (a browser secure context), permit clipboard access, or select text manually.
- **Port busy:** stop the earlier instance. If changing ports, update the Vite proxy and backend origin allowlist together.

## Extension points

Keep additional providers and retrieval on the backend, extend the message schema for attachments, and add authenticated ownership before account synchronization. Voice input can feed the existing composer; voice output can consume completed assistant messages. Uploads, RAG, web search, vector memory and speech are intentionally left for future versions.

Ollama protocol reference: [chat API](https://docs.ollama.com/api/chat). FastAPI streaming reference: [StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse).
