# Repository Guidelines
-始终用中文回答问题！
## Project Structure & Modules
- Backend (Python/FastAPI): `backend.py` (app entry), domain code in `llm_interface.py`, `multi_source_engine.py`, `conversation_manager.py`, and folders: `langchain_workflows/`, `adapters/`, `models/`, `prompts/`.
- Frontend (React/Vite/TS): `frontend/` with `src/`, `public/`, `package.json`.
- Data & runtime: `conversations/`, `data/`, `.env` files; Dockerfiles: `Dockerfile.backend`, `frontend/Dockerfile`.
- Tests: Python tests like `test_search_improvements.py` (root). Add more under `tests/` or alongside modules as `test_*.py`.

## Build, Test, Run
- Backend
  - Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
  - Dev server: `uvicorn backend:app --reload` (listens to FastAPI app in `backend.py`).
  - Tests: `pytest -q`. Type check: `mypy .`.
- Frontend (`frontend/`)
  - Install: `npm ci` (or `npm install`)
  - Dev: `npm run dev` | Build: `npm run build` | Lint: `npm run lint` | Preview: `npm run preview`.

## Coding Style & Naming
- Python: 4-space indents, type hints required; modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`. Keep pure logic in modules; keep FastAPI routes thin.
- TypeScript/React: components `PascalCase.tsx`, hooks `useX` naming, prefer named exports; follow ESLint defaults in `frontend/`.
- Tools: `mypy` (types), `pytest` (tests), `eslint` (frontend). Run before PRs.

## Testing Guidelines
- Use `pytest`; name files `test_*.py` and functions `test_*`. For async tests, add `@pytest.mark.asyncio`.
- Cover core flows: query analysis -> search (`multi_source_engine.py`) -> responses; mock network/LLM calls where possible.
- Run fast tests locally; leave long-running or networked tests behind a marker (e.g., `-m slow`).

## Commit & PR Guidelines
- Commits are short and focused; messages often summarize in Chinese with date/version (see `git log`). Prefer imperative: e.g., `backend: 修复流式传输`, `3.0.1 解决埋点问题`.
- PRs: include what/why, test steps, affected modules, and screenshots for UI changes. Link issues/tasks. Ensure `pytest`, `mypy`, and `npm run lint` pass.

## Security & Config
- Do not commit secrets. Backend reads `.env` via `python-dotenv`; frontend has `frontend/.env.example`-copy to `.env` and fill keys (LLM providers, Supabase, etc.).
- Prefer local `.env` overrides; never hardcode tokens in code.
