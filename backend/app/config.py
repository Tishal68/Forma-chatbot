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
        return os.getenv('AUTH_USERNAME', '')

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


settings = Settings()

