# Contributing to Forma

Thank you for your interest in contributing to Forma!

## Development Setup

### Backend (FastAPI + Python 3.11+)
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt pytest
```

Run tests:
```bash
pytest
```

Run backend server:
```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Frontend (React + Vite + TypeScript)
```bash
cd frontend
npm install
npm run dev
```

Build for production:
```bash
npm run build
```

## Guidelines
1. Keep the codebase clean and modular.
2. Adhere to security best practices (validate inputs, protect API endpoints, avoid committing secrets).
3. Ensure all automated tests (`pytest`) pass before opening a Pull Request.
