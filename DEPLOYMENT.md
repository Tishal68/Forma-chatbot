# Deploy Forma on Render or Railway

The Dockerfile builds React and serves it with FastAPI as **one web service**. No separate frontend deployment or CORS setup is needed. The process listens on the host-provided `PORT` and uses one worker. SQLite requires persistent storage at `/var/data` and one replica.

## Before deploying: AI Providers

Forma supports 4 AI inference providers:
- **Groq** (`GROQ_API_KEY`): Ultra-fast cloud inference (Llama 3.3 70B, DeepSeek R1 Distill). Recommended for quick, free-tier setup.
- **Google Gemini** (`GEMINI_API_KEY`): Gemini 2.0 Flash and Gemini 1.5 Pro via Google AI Studio.
- **OpenAI** (`OPENAI_API_KEY`): GPT-4o, GPT-4o-mini, o3-mini.
- **Ollama** (`OLLAMA_BASE_URL`): Self-hosted offline inference (e.g. `llama3.2`, `mistral`, `deepseek-r1`). **Ollama is completely optional.**

At least one provider must be configured for production startup. When deploying to cloud environments like Render or Railway, you do **not** need to run or host an Ollama instance — simply configure one or more cloud API keys (`GROQ_API_KEY`, etc.) in your environment variables.

All API keys remain strictly secure on the backend. The frontend queries `/api/models`, which checks server-side environment variables, probes provider health, and presents only configured, operational providers and models in the UI selector.

## Access Model & Visitor Privacy

Forma provides **anonymous, isolated visitor sessions** with zero login friction:
- **No Sign-In Popup**: Visitors can open the webpage and start chatting immediately without an account, password prompt, or browser sign-in modal.
- **Strict Data Isolation**: Each visitor is automatically issued a cryptographically signed, `HttpOnly`, `SameSite=Lax` session cookie (`forma_session`). Conversations, messages, attachments, searches, and file downloads are strictly scoped to the visitor's session.
- **Resource Protection**: Endpoints enforce visitor ownership across every path (`list`, `create`, `read`, `rename`, `delete`, `upload`, `download`, `search`, `regenerate`, `stop`, `streaming`). Requesting or modifying another visitor's conversation or file returns `404 Not Found`.
- **Scoped "Clear All"**: Selecting "Clear all conversations" removes only the current visitor's database records and disk attachments. Other visitors' chats and files are unaffected.
- **Private Legacy Archive**: Any chats and attachments created before this update are preserved in a private legacy archive and are never exposed to public anonymous visitors.
- **Browser Cookie Notice**: Anonymous chats are tied to the visitor's browser session cookie. If browser cookies or site data are cleared, the anonymous session resets and past chats will no longer be accessible.

### When to remove AUTH_USERNAME and AUTH_PASSWORD

- **Public Deployment (Default)**: You can safely remove `AUTH_USERNAME` and `AUTH_PASSWORD` (or leave them blank) in your Render or Railway service environment variables. The server will boot into public mode with complete visitor isolation, anti-DDoS IP rate limiting, and spending controls.
- **Private Instance (Optional)**: If you want to restrict the entire application to yourself with HTTP Basic Authentication, set `AUTH_USERNAME` and `AUTH_PASSWORD` (must be at least 16 characters). If both are set, visitors must authenticate before accessing the application.

## Enterprise Security & Spending Controls

Public deployments are protected by multi-layered defenses:
1. **Trusted Proxy & Anti-Spoofing IP Resolution**:
   - Proxy headers (`X-Forwarded-For`, `X-Real-IP`) are **only** trusted when the direct connection originates from a configured `TRUSTED_PROXIES` address (defaults to `127.0.0.1,::1`, plus cloud proxy ranges like `10.0.0.0/8`).
   - For direct, untrusted connections, proxy headers are ignored, preventing attackers from bypassing IP rate limits via forged headers.
2. **AI Provider Spending Controls & Rate Limiting**:
   - **Per-IP limits**: Sliding window rate limits prevent DDoS and automated scraping (`RATE_LIMIT_CHAT_PER_MINUTE=30`, general API `240/min`).
   - **Per-Visitor limits**: Prevents token exhaustion and credit draining (`RATE_LIMIT_VISITOR_CHAT_PER_MINUTE=15`, daily allowance `RATE_LIMIT_VISITOR_CHAT_PER_DAY=200`).
   - **Concurrency limits**: Maximum 1 active generation per visitor session (`MAX_CONCURRENT_PER_VISITOR=1`) and instance-wide global concurrency limits (`MAX_CONCURRENT_GLOBAL=10`).
   - **Storage & Upload limits**: File upload validation, max 25MB per file, max 20 attachments per chat, and max 100MB cumulative storage per visitor (`MAX_VISITOR_STORAGE_MB=100`).
   - Single-worker SQLite execution ensures consistent in-memory tracking without race conditions.
3. **CSRF & Origin Protection**:
   - Mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) require an allowed `Origin` or `Referer` and validate `X-CSRF-Token` against the `forma_csrf` cookie.
   - Cross-origin requests from unauthorized origins return `403 Forbidden`.
4. **OWASP Hardening Headers**:
   - Responses include `Content-Security-Policy`, `X-Frame-Options: DENY` (anti-clickjacking), `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`, and HSTS transport encryption in production.
5. **API Key Confidentiality**:
   - All AI keys (`GROQ_API_KEY`, etc.) remain strictly on the backend server and are never delivered to the client browser.

## Render Deployment

1. In Render, choose **New → Blueprint** and connect `Tishal68/Forma-chatbot` (or fork to your own account).
2. Render reads `render.yaml`. It provisions a Docker web service and a 1 GB persistent disk for your chat history.
3. In the Render service settings / environment variables:
   - Configure at least one AI provider variable:
     - `GROQ_API_KEY`: Ultra-fast & free at [console.groq.com/keys](https://console.groq.com/keys) (recommended)
     - `GEMINI_API_KEY`: Google AI Studio key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
     - `OPENAI_API_KEY`: OpenAI platform key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
     - `OLLAMA_BASE_URL`: Accessible remote Ollama server (optional, leave blank if using cloud keys).
   - `AUTH_USERNAME` / `AUTH_PASSWORD`: Optional. Leave empty/unset for public zero-login access.
4. Deploy the service.
5. Open your service's `https://<service-name>.onrender.com` URL. Anyone can start chatting immediately with private session isolation.

Render's standard public URL is permitted automatically through `RENDER_EXTERNAL_URL`. For a custom domain, set `ALLOWED_ORIGINS=https://chat.your-domain.com`.

## Railway

1. Create a project → **Deploy from GitHub repo** → `Tishal68/Forma-chatbot`.
2. Railway detects `Dockerfile` and `railway.json`.
3. Add a **Volume**, mounted at `/var/data`, before relying on chat persistence. Keep one replica.
4. Configure service variables:

```dotenv
APP_ENV=production
DATABASE_PATH=/var/data/chat.db
ATTACHMENTS_DIR=/var/data/attachments
# Set at least one provider (cloud or Ollama):
GROQ_API_KEY=gsk_...
# GEMINI_API_KEY=...
# OPENAI_API_KEY=sk-proj-...
# OLLAMA_BASE_URL=https://your-reachable-ollama-server.example
# Optional: AUTH_USERNAME / AUTH_PASSWORD only if you want a private instance
```

5. Generate a public domain under Networking, then deploy. The service reads Railway's `PORT`; do not override the start command.
6. Open the HTTPS URL and verify model connectivity in Settings.

## Local Container Check

With Docker installed and your production variables saved in an uncommitted `.env`:

```sh
docker build -t forma .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -e APP_ENV=production -v forma-data:/var/data forma
```

## Validation and Operations

- GitHub Actions runs backend tests, builds the frontend, builds Docker, and smoke-tests container health and security.
- `/api/health` is public and returns only app/database liveness.
- Keep one process/replica; live generation ownership is held in process memory. Do not use multiple workers with this SQLite version.
