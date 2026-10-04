import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file from project root
load_dotenv(ROOT / '.env')


class Settings:
    @property
    def APP_ENV(self) -> str:
        return os.getenv('APP_ENV', 'development')

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == 'production'

    @property
    def AUTH_USERNAME(self) -> str:
        return os.getenv('AUTH_USERNAME', '').strip()

    @property
    def AUTH_PASSWORD(self) -> str:
        return os.getenv('AUTH_PASSWORD', '')

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')

    @property
    def OLLAMA_API_KEY(self) -> str | None:
        return os.getenv('OLLAMA_API_KEY') or None

    @property
    def OLLAMA_MODEL(self) -> str:
        return os.getenv('OLLAMA_MODEL', 'llama3.2')

    @property
    def CONTEXT_TOKENS(self) -> int:
        return int(os.getenv('CONTEXT_TOKENS', '8192'))

    @property
    def OUTPUT_TOKENS(self) -> int:
        return int(os.getenv('OUTPUT_TOKENS', '4096'))

    @property
    def GENERATION_TIMEOUT(self) -> float:
        return float(os.getenv('GENERATION_TIMEOUT', '300'))

    @property
    def ATTACHMENTS_DIR(self) -> Path:
        dir_path = Path(os.getenv('ATTACHMENTS_DIR', 'data/attachments'))
        if not dir_path.is_absolute():
            dir_path = ROOT / dir_path
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @property
    def MAX_ATTACHMENT_SIZE_BYTES(self) -> int:
        mb = int(os.getenv('MAX_ATTACHMENT_SIZE_MB', '25'))
        return mb * 1024 * 1024

    @property
    def SEARCH_PROVIDER(self) -> str:
        return os.getenv('SEARCH_PROVIDER', 'duckduckgo').lower()

    @property
    def TAVILY_API_KEY(self) -> str:
        return os.getenv('TAVILY_API_KEY', '')

    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv('BRAVE_API_KEY', '')

    @property
    def SERPAPI_API_KEY(self) -> str:
        return os.getenv('SERPAPI_API_KEY', '')

    # Session & Security Settings
    @property
    def SESSION_COOKIE_NAME(self) -> str:
        return os.getenv('SESSION_COOKIE_NAME', 'forma_session')

    @property
    def CSRF_COOKIE_NAME(self) -> str:
        return os.getenv('CSRF_COOKIE_NAME', 'forma_csrf')

    _cached_session_secret: str | None = None

    def reset_session_secret_cache(self) -> None:
        """Clear cached session secret (primarily for testing)."""
        self._cached_session_secret = None

    def get_session_secret_path(self) -> Path:
        """
        Determine persistent path for storing SESSION_SECRET.
        In production, prioritizes the persistent volume directory containing DATABASE_PATH
        (defaults to /var/data/.session_secret in Docker / Railway / Render).
        """
        db_env = os.getenv('DATABASE_PATH')
        if db_env:
            return Path(db_env).resolve().parent / '.session_secret'
        var_data = Path('/var/data')
        if var_data.exists() or self.is_production:
            return var_data / '.session_secret'
        return ROOT / 'data' / '.session_secret'

    @property
    def SESSION_SECRET(self) -> str:
        secret = os.getenv('SESSION_SECRET', '').strip()
        if secret:
            self._cached_session_secret = secret
            return secret

        if self._cached_session_secret:
            return self._cached_session_secret

        secret_file = self.get_session_secret_path()
        if secret_file.exists():
            try:
                cached = secret_file.read_text(encoding='utf-8').strip()
                if cached:
                    self._cached_session_secret = cached
                    return cached
            except OSError as exc:
                if self.is_production:
                    raise RuntimeError(
                        f"Production requires a stable SESSION_SECRET environment variable or readable secret file at {secret_file}. Failed to read: {exc}"
                    )

        import secrets
        generated = secrets.token_hex(32)
        try:
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(generated, encoding='utf-8')
            self._cached_session_secret = generated
            return generated
        except OSError as exc:
            if self.is_production:
                raise RuntimeError(
                    f"In production, SESSION_SECRET must be set in environment variables or persisted on /var/data (attempted {secret_file}): {exc}. "
                    "Cannot silently generate ephemeral session secret."
                )
            import logging
            logging.getLogger('forma').warning(
                "Could not persist SESSION_SECRET to %s: %s; using memoized in-memory secret for process",
                secret_file,
                exc,
            )
            self._cached_session_secret = generated
            return generated

    @property
    def SESSION_MAX_AGE_SECONDS(self) -> int:
        return int(os.getenv('SESSION_MAX_AGE_SECONDS', str(365 * 24 * 3600)))

    @property
    def TRUSTED_PROXIES(self) -> set[str]:
        raw = os.getenv('TRUSTED_PROXIES', '127.0.0.1,::1')
        return {p.strip() for p in raw.split(',') if p.strip()}

    # Rate Limiting & Spending Controls
    @property
    def RATE_LIMIT_CHAT_PER_MINUTE(self) -> int:
        return int(os.getenv('RATE_LIMIT_CHAT_PER_MINUTE', '30'))

    @property
    def RATE_LIMIT_VISITOR_CHAT_PER_MINUTE(self) -> int:
        return int(os.getenv('RATE_LIMIT_VISITOR_CHAT_PER_MINUTE', '15'))

    @property
    def RATE_LIMIT_VISITOR_CHAT_PER_DAY(self) -> int:
        return int(os.getenv('RATE_LIMIT_VISITOR_CHAT_PER_DAY', '200'))

    @property
    def RATE_LIMIT_ATTACHMENTS_PER_MINUTE(self) -> int:
        return int(os.getenv('RATE_LIMIT_ATTACHMENTS_PER_MINUTE', '40'))

    @property
    def RATE_LIMIT_GENERAL_PER_MINUTE(self) -> int:
        return int(os.getenv('RATE_LIMIT_GENERAL_PER_MINUTE', '240'))

    # Concurrency & Storage Limits
    @property
    def MAX_CONCURRENT_PER_VISITOR(self) -> int:
        return int(os.getenv('MAX_CONCURRENT_PER_VISITOR', '1'))

    @property
    def MAX_CONCURRENT_GLOBAL(self) -> int:
        return int(os.getenv('MAX_CONCURRENT_GLOBAL', '10'))

    @property
    def MAX_VISITOR_STORAGE_BYTES(self) -> int:
        mb = int(os.getenv('MAX_VISITOR_STORAGE_MB', '100'))
        return mb * 1024 * 1024

    @property
    def MAX_ATTACHMENTS_PER_CONVERSATION(self) -> int:
        return int(os.getenv('MAX_ATTACHMENTS_PER_CONVERSATION', '20'))

    @property
    def MAX_CONVERSATIONS_PER_VISITOR(self) -> int:
        return int(os.getenv('MAX_CONVERSATIONS_PER_VISITOR', '100'))


settings = Settings()

