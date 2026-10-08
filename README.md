# Forma Chatbot

Forma is a chatbot I built as a college project to learn about AI APIs, model selection, and full-stack development.

It uses React and TypeScript for the frontend, FastAPI for the backend, and SQLite to save chats and preferences.

## Features

- **Multi-Model Orchestration**: Chat with models from Groq, Gemini, OpenAI, or a local Ollama server.
- **Intelligent Routing & Reliability**: Auto mode evaluates task intent (reasoning, math, coding, documents, research) and picks the best model with exponential backoff cooldown management across HTTP 429/5xx errors.
- **Hybrid RAG Engine**: Indexes uploaded PDFs, DOCXs, TXT, and code into SQLite FTS5 chunks and dense vector embeddings with Reciprocal Rank Fusion (RRF).
- **Categorized Long-Term Memory**: Automatically captures and organizes profile, project, episodic, and semantic facts with JSON export/import and credential protection.
- **Agent Mode & Safe Tool Suite**: Multi-step autonomous agent with AST-validated Python sandbox, GitHub repo inspector, structured CSV/JSON processor, and audit logging.
- **Rich Interaction**: Real-time web search, document uploads, vision support, image generation, message editing, regeneration, and custom instructions.
- **Privacy & Security**: Single-tenant architecture with visitor isolation, CSRF protection, and zero hardcoded secrets.

Manual model selections stay selected. API keys are stored securely on the backend. Chats and preferences belong to the current browser session. Full workspace backups are exportable anytime.

## Run locally

You need Python 3.11+ and Node.js 20+.

```bash
git clone https://github.com/Tishal68/Forma-chatbot.git
cd Forma-chatbot
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` and copy the example with `Copy-Item .env.example .env`.

Add at least one API key to `.env`: `GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`. To use local models, run Ollama and set `OLLAMA_BASE_URL` instead.

Start the backend:

```bash
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173.

## Tests

From the project folder:

```bash
python -m pytest -q
```

From the frontend folder:

```bash
npm run build
npx playwright install chromium
npm run test:ui
```

Provider responses are mocked in the test suite (114+ backend unit/integration tests).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architectural documentation, systems diagrams, and component breakdowns.

## Deployment

The Docker setup serves the frontend and backend together. Render and Railway configuration files are included. See [DEPLOYMENT.md](DEPLOYMENT.md) for setup instructions.

## Current limitations

- Replies depend on configured API keys or local Ollama availability.
- Image generation requires a local or remote model supporting image synthesis.

## License

[MIT](LICENSE)
