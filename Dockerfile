FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 APP_ENV=production DATABASE_PATH=/var/data/chat.db \
    OLLAMA_BASE_URL=http://localhost:11434
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 forma && useradd --uid 10001 --gid forma --no-create-home forma \
    && mkdir -p /var/data && chown forma:forma /var/data
COPY backend/requirements-lock.txt ./backend/requirements-lock.txt
RUN pip install --no-cache-dir -r backend/requirements-lock.txt
COPY backend/app ./backend/app
COPY --from=frontend /build/dist ./frontend/dist
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health', timeout=4)"
ENTRYPOINT ["/entrypoint.sh"]
