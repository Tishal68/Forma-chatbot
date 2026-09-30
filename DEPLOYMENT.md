# Deploy Forma on Render or Railway

The Dockerfile builds React and serves it with FastAPI as **one web service**. No separate frontend deployment or CORS setup is needed. The process listens on the host-provided `PORT` and uses one worker. SQLite requires persistent storage at `/var/data` and one replica.

## Before deploying: AI Providers

Forma supports 5 AI inference providers:
- **Groq** (`GROQ_API_KEY`): Ultra-fast cloud inference (Llama 3.3 70B, DeepSeek R1 Distill). Recommended for quick, free-tier setup.
- **OpenRouter** (`OPENROUTER_API_KEY`): Unified access to Claude 3.5 Sonnet, DeepSeek R1, Llama 3.3, and more.
- **Google Gemini** (`GEMINI_API_KEY`): Gemini 2.0 Flash and Gemini 1.5 Pro via Google AI Studio.
- **OpenAI** (`OPENAI_API_KEY`): GPT-4o, GPT-4o-mini, o3-mini.
- **Ollama** (`OLLAMA_BASE_URL`): Self-hosted offline inference (e.g. `llama3.2`, `mistral`, `deepseek-r1`). **Ollama is completely optional.**

At least one provider must be configured for production startup. When deploying to cloud environments like Render or Railway, you do **not** need to run or host an Ollama instance — simply configure one or more cloud API keys (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, etc.) in your environment variables.

All API keys remain strictly secure on the backend. The frontend queries `/api/models`, which checks server-side environment variables, probes provider health, and presents only configured, operational providers and models in the UI selector.

## Render Deployment

1. In Render, choose **New → Blueprint** and connect `Tishal68/Forma-chatbot` (or fork to your own account).
2. Render reads `render.yaml`. It provisions a Docker web service and a 1 GB persistent disk for your chat history.
3. In the Render service settings / environment variables:
   - Provide `AUTH_USERNAME` (e.g. `admin`).
   - `AUTH_PASSWORD` is automatically generated (minimum 16 characters); retrieve it from the service dashboard.
   - Set at least one cloud provider API key, such as:
     - `GROQ_API_KEY`: Get a free key at [console.groq.com](https://console.groq.com/keys)
     - `OPENROUTER_API_KEY`: Get a key at [openrouter.ai](https://openrouter.ai/keys)
     - `GEMINI_API_KEY`: Get a key at [aistudio.google.com](https://aistudio.google.com/app/apikey)
     - `OPENAI_API_KEY`: Get a key at [platform.openai.com](https://platform.openai.com/api-keys)
   - Leave `OLLAMA_BASE_URL` blank unless you run a private, reachable Ollama server.
4. Deploy the service.
5. Open your service's `https://<service-name>.onrender.com` URL. Sign in with your `AUTH_USERNAME` and generated `AUTH_PASSWORD`.
6. Forma automatically detects your working cloud provider and selects it by default.

Render's standard public URL is permitted automatically through `RENDER_EXTERNAL_URL`. For a custom domain, set `ALLOWED_ORIGINS=https://chat.your-domain.com` (comma-separate multiple origins, no paths or trailing slash).

## Railway

1. Create a project → **Deploy from GitHub repo** → `Tishal68/Forma-chatbot`.
2. Railway detects `Dockerfile` and `railway.json`.
3. Add a **Volume**, mounted at `/var/data`, before relying on chat persistence. Keep one replica.
4. Configure service variables:

```dotenv
APP_ENV=production
DATABASE_PATH=/var/data/chat.db
AUTH_USERNAME=your-chosen-username
AUTH_PASSWORD=replace-with-a-random-password-at-least-16-characters
# Set at least one provider (cloud or Ollama):
GROQ_API_KEY=gsk_...
# OPENROUTER_API_KEY=sk-or-...
# GEMINI_API_KEY=...
# OPENAI_API_KEY=sk-proj-...
# OLLAMA_BASE_URL=https://your-reachable-ollama-server.example
```

The sample password is a placeholder, not a credential to use. Generate a password locally, for example with `python -c "import secrets; print(secrets.token_urlsafe(32))"`, and paste it into Railway's secret variables. Add `OLLAMA_API_KEY` if using private Ollama.

5. Generate a public domain under Networking, then deploy. The service reads Railway's `PORT`; do not override the start command.
6. Sign in at the HTTPS URL and verify model connectivity in Settings.

The Railway domain is permitted through `RAILWAY_PUBLIC_DOMAIN`. If it is unavailable or you use a custom domain, set `ALLOWED_ORIGINS` explicitly to that HTTPS origin.

## Access model

This is **one password-protected shared workspace**, not separate per-user accounts. Anyone who knows its password can read and modify all conversations. Production startup refuses to run without a username and a password of at least 16 characters. HTTP Basic credentials are managed by the browser; no password is bundled into JavaScript. Use HTTPS on hosted deployments. Close the browser session to clear cached authentication, or rotate the password to revoke access.

Local development remains password-free unless you explicitly set both authentication variables. Conversation content lives on the deployment's volume, not on a visitor's device. Back up that volume/database and do not delete the disk when redeploying.

## Local container check

With Docker installed and your production variables saved in an uncommitted `.env`:

```sh
docker build -t forma .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -e APP_ENV=production -v forma-data:/var/data forma
```

The image defaults to production mode and runs the application as a non-root user after preparing volume ownership. On Docker Desktop, a host Ollama server can be reached with `http://host.docker.internal:11434` if Ollama accepts that connection. This hostname is not a remote deployment solution.

## Validation and operations

- GitHub Actions runs backend tests, builds the frontend, builds Docker, and smoke-tests production authentication and the health endpoint on Linux.
- `/api/health` is intentionally public and returns only app/database liveness. Other pages, docs and APIs are protected when credentials are set.
- Settings → Refresh installed models checks the AI server. A missing or unreachable model produces a user-facing error.
- Keep one process/replica; live generation ownership is held in process memory. Do not use multiple workers with this SQLite version.
- Model summaries may delay first tokens in long chats. Check your hosting proxy's response timeout for lengthy generation.
- Dependencies are locked; review updates and rerun CI before deployment.

Official references: [Render Blueprint specification](https://render.com/docs/blueprint-spec), [Railway config as code](https://docs.railway.com/config-as-code/reference).
