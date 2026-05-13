# AGENTS.md

This guide is for coding agents working in the `tanpopo` repository.
It documents the practical commands and coding conventions observed in the codebase.

## 1) Project Snapshot
- Language: Python 3.10+
- Runtime style: async bot service (WebSocket + MongoDB + LLM APIs)
- Entry point: `run.py`
- Main code: `src/`
- Utility scripts: `script/`
- Deployment path: Docker / docker-compose

## 2) Repository Layout
- `run.py`: top-level startup script
- `src/ws/__init__.py`: WS client/server wrapper
- `src/event/__init__.py`: message event and segment parsing
- `src/bot/bot.py`: orchestration and message handling loop
- `src/bot/config.py`: YAML config loading + global config object
- `src/bot/database.py`: MongoDB access wrapper
- `src/bot/llmapi.py`: model API calls (chat, embedding, rerank)
- `src/bot/memory.py`: memory build/recall/forget logic
- `script/init_memory_db.py`: seed initial memory records
- `script/memory_db_query_test.py`: memory query debug script
- `template/config_template.yaml`: config template

## 3) Environment Setup
### Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp template/config_template.yaml config.yaml
```
Also prepare:
- `init_memory_config.yaml` (optional; auto-copied from template when absent)
- reachable MongoDB instance (default `mongodb://localhost:27017/`)
- valid LLM credentials in `config.yaml` (`llm_auth.api_key`, `llm_auth.base_url`)

### Docker setup
```bash
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker-compose up -d --build
```
Notes:
- Docker image installs from `requirements.txt`
- Container startup runs: `./start.sh && python script/init_memory_db.py && python run.py`

## 4) Build, Lint, and Test Commands
This repository does not define Makefile/tox/pytest config yet.
Use the commands below as the standard workflow.

### Build / run
- Start app locally: `python run.py`
- Seed memory DB once: `python script/init_memory_db.py`
- Start full stack (Docker): `docker-compose up -d --build`
- Rebuild image only: `docker build -t tanpopo .`

### Lint / static checks
- Syntax check all Python files: `python -m compileall src script run.py`
- Optional style lint (if installed): `ruff check src script run.py`
- Optional format check (if installed): `black --check src script run.py`

### Tests
Current state:
- No dedicated `tests/` suite is checked in.
- Available validation script: `python script/memory_db_query_test.py`
When a pytest suite is present, use:
- Run all tests: `pytest -q`
- Run one file: `pytest tests/path/test_x.py -q`
- Run a single test: `pytest tests/path/test_x.py::test_case_name -q`
- Run one test method: `pytest tests/path/test_x.py::TestClass::test_method -q`
If using `unittest` style instead:
- `python -m unittest tests.test_module.TestClass.test_method`

## 5) Cursor / Copilot Rules
Checked locations:
- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`
Result:
- No Cursor or Copilot instruction files were found in this repository.
- If these files are added later, treat them as higher-priority constraints.

## 6) Code Style Conventions
Use existing code patterns unless the user requests a refactor.

### Imports
- Group imports in this order: stdlib, third-party, local modules.
- Separate groups with one blank line.
- Prefer relative imports within `src` packages (e.g. `from .x import Y`, `from ..event import MessageEvent`).
- Avoid wildcard imports.

### Formatting
- Follow PEP 8 baseline (4-space indent, trailing newline, readable line length).
- Keep functions small where practical; split complex flows into helpers.
- Preserve existing Chinese-language logs/docstrings where touched.
- Do not add decorative comments; only add comments for non-obvious logic.

### Types
- Add type hints for new/changed function signatures.
- Prefer built-in generics (`list[str]`, `dict[str, str]`) on Python 3.10+.
- Keep return types explicit, especially for async methods.
- Keep dataclass fields typed and use `field(default_factory=...)` for mutable defaults.

### Naming
- `snake_case`: functions, variables, module names.
- `PascalCase`: classes.
- `UPPER_SNAKE_CASE`: constants.
- Use descriptive names for event/message payload variables (`message_event`, `chat_history`, etc.).

### Async and concurrency
- Core bot flows are async; prefer async-compatible changes.
- For background loops, use `asyncio.create_task(...)` and `asyncio.sleep(...)` patterns.
- Protect shared mutable state with `asyncio.Lock` (see memory manager patterns).
- Avoid blocking calls on the event loop; move heavy sync work with `asyncio.to_thread(...)`.

### Error handling and resilience
- Wrap external I/O boundaries with `try/except` (LLM calls, DB calls, network parsing).
- Log failures via module logger; include concise context.
- Use retries for transient model/network failures (see `max_retrys` usage).
- Return safe defaults on recoverable parse failures when appropriate.
- Raise exceptions only when callers should explicitly handle startup/config failures.

### Logging
- Use `register_logger("module name", global_config.log_level)`.
- Keep one module-level logger per file.
- Prefer structured, concise log messages over print statements.

### Configuration and secrets
- Read runtime settings from `global_config`; avoid hardcoding host/ports/models.
- Never commit real API keys or sensitive values.
- Keep `config.yaml` local; it is gitignored.

### Data and DB access
- Use `Database` wrapper methods instead of direct raw client calls where possible.
- Keep memory/document payload keys consistent with existing schema (`_id`, `summary`, `embedding`, etc.).
- Preserve backward compatibility when adding new document fields.

### Testing guidance for new work
- Add new tests under a dedicated `tests/` directory.
- Prefer pytest naming: `tests/**/test_*.py`, `test_*` functions.
- For async logic, test happy path + failure path (timeouts, malformed response, empty result).
- For DB-related logic, isolate side effects or use dedicated test collections.

## 7) Agent Working Rules (Repo-specific)
- Make minimal, focused diffs; avoid opportunistic rewrites.
- Do not silently change config schema without updating templates/docs.
- If you add tooling (ruff/black/pytest config), document exact commands in this file.
- Prefer backward-compatible changes to bot event formats and memory records.
