# Deploy Forma on Render or Railway

The Dockerfile builds React and serves it with FastAPI as **one web service**. No separate frontend deployment or CORS setup is needed. The process listens on the host-provided `PORT` and uses one worker. SQLite requires persistent storage at `/var/data` and one replica.

## Before deploying: connect an AI server

The web service does **not** include an Ollama model or run inference itself. Set `OLLAMA_BASE_URL` to an Ollama server reachable **from the hosting provider**, not your laptop's `localhost`. The service must implement Ollama's `/api/tags` and `/api/chat` endpoints. Install your selected model on that server first.

Options include a separate private Ollama service on a sufficiently provisioned server, or an authenticated HTTPS Ollama-compatible endpoint. Set `OLLAMA_API_KEY` only if the endpoint expects a bearer token; ordinary private-network Ollama needs no key. Do not expose unauthenticated Ollama directly to the public Internet. An OpenAI-only API endpoint is not compatible with this integration.

The lightweight web container and the AI server have different hardware requirements. Size the AI server for your model. A successful web health check confirms the app/database, **not** AI model connectivity. After deployment, open Settings → Refresh installed models, then send a message to verify the full connection.

## Render

1. In Render, choose **New → Blueprint** and connect `Tishal68/Forma-chatbot`.
2. Render reads `render.yaml`. It provisions a Docker web service and a 1 GB persistent disk. This uses the **paid Starter plan**, because persistent history needs a disk. Review the dashboard cost before deploying.
3. Supply `AUTH_USERNAME`, a reachable `OLLAMA_BASE_URL`, and `OLLAMA_API_KEY` (leave it blank for an unauthenticated private endpoint). Render generates `AUTH_PASSWORD` automatically; retrieve it from the service's environment settings after creation.
4. Change `OLLAMA_MODEL` if your AI server uses a different model. Deploy.
5. Open the provided HTTPS URL. The browser asks for the workspace username/password. Use the environment values from step 3.

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
OLLAMA_BASE_URL=https://your-reachable-ollama-server.example
OLLAMA_MODEL=llama3.2
```

The sample password is a placeholder, not a credential to use. Generate a password locally, for example with `python -c "import secrets; print(secrets.token_urlsafe(32))"`, and paste it into Railway's secret variables. Add `OLLAMA_API_KEY` if needed.

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
