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


settings = Settings()
