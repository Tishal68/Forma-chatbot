# Forma Chatbot

Forma is a chatbot I built as a college project to learn about AI APIs, model selection, and full-stack development.

It uses React and TypeScript for the frontend, FastAPI for the backend, and SQLite to save chats and preferences.

## Features

- Chat with models from Groq, Gemini, OpenAI, or a local Ollama server.
- Auto chooses a model for each message and tries up to two compatible backups if it fails before replying.
- Save preferences and memories in Settings → Personalization.
- Upload documents and images, and ask follow-up questions about them.
- Search the web, edit messages, regenerate replies, and manage chat history.
- Use light or dark mode on desktop and mobile.

Manual model selections stay selected. API keys are stored on the backend. Chats and preferences belong to the current browser session and do not sync across devices.

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

Provider responses are mocked in the tests.

## Deployment

The Docker setup serves the frontend and backend together. Render and Railway configuration files are included. See [DEPLOYMENT.md](DEPLOYMENT.md) for setup instructions.

## Current limitations

- Replies depend on the available models and their API limits.
- Document and memory retrieval uses keyword matching rather than embeddings.
- Image generation needs an Ollama server that supports it.

## License

[MIT](LICENSE)
