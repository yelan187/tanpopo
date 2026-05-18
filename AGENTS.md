# AGENTS.md

This guide is intended for coding agents working in the `tanpopo` repository.
It documents the practical commands and coding conventions observed in the codebase.

## 1) Project Snapshot
- Language: Python 3.10+
- Runtime style: async QQ bot service (WebSocket + OpenHands SDK + MCP tools)
- Entry point: `run.py`
- Main code: `src/`
- Deployment path: Docker / docker-compose

Current default architecture:
- `run.py` routes OneBot message events to `src/agent/core.py` (`AgentCore`)
- `AgentCore` uses one shared OpenHands `Agent` + per-session `Conversation`
- QQ I/O and common actions are exposed via MCP server `src/mcp/qqio.py`
- OpenHands default terminal/file tools are disabled on the runtime path; capabilities should be added through configured MCP servers
- TTADK-specific routing has been removed; runtime now targets generic OpenAI-compatible endpoints

## 2) Repository Layout
- `run.py`: top-level startup script
- `src/agent/core.py`: OpenHands conversation loop, per-session lock/isolation, MCP wiring
- `src/adapters/onebot.py`: OneBot event to generic agent message adapter
- `src/runtime/`: shared runtime config, logging, registry, and MCP server normalization
- `src/mcp/qqio.py`: FastMCP server with OneBot APIs + memory tools
- `.agents/mcps/`: tracked home for agent-authored MCP plugins
- `src/ws/__init__.py`: WS client/server wrapper
- `src/event/__init__.py`: message event and segment parsing
- `template/config_template.yaml`: config template

## 3) Environment Setup
### Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp template/config_template.yaml config.yaml
```
Also prepare valid LLM credentials in `config.yaml` (`llm_auth.api_key`, `llm_auth.base_url`).

### Docker setup
```bash
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker-compose up -d --build
```
Notes:
- Docker image installs from `requirements.txt`
- Container startup runs: `./start.sh && python run.py`

## 4) Build, Lint, and Test Commands
This repository does not define Makefile/tox/pytest config yet.
Use the commands below as the standard workflow.

### Build / run
- Start app locally: `python run.py`
- Start full stack (Docker): `docker-compose up -d --build`
- Rebuild image only: `docker build -t tanpopo .`
- Rebuild+restart tanpopo only: `docker compose up -d --build tanpopo`

### Lint / static checks
- Syntax check all Python files: `python -m compileall src run.py`
- Fast check for agent path: `python -m compileall src/agent src/adapters src/runtime src/mcp`
- Optional style lint (if installed): `ruff check src script run.py`
- Optional format check (if installed): `black --check src script run.py`

### Tests
Current state:
- No dedicated `tests/` suite is checked in.
When a pytest suite is present, use:
- Run all tests: `pytest -q`
- Run one file: `pytest tests/path/test_x.py -q`
- Run a single test: `pytest tests/path/test_x.py::test_case_name -q`
- Run one test method: `pytest tests/path/test_x.py::TestClass::test_method -q`
If using `unittest` style instead:
- `python -m unittest tests.test_module.TestClass.test_method`

### OpenHands runtime sanity checks
- Verify SDK import: `python -c "from openhands.sdk import LLM, Agent, Conversation, Tool; print('ok')"`
- Verify container-loaded config: `docker compose exec tanpopo python -c "from src.runtime import global_config; print(global_config.agent_config.get('openhands', {}))"`
- Tail latest tanpopo logs: `docker compose logs --no-color --since=60s tanpopo`

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
- Let the OpenHands SDK handle transient model/network retries unless a narrower retry policy is explicitly needed.
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
- For OpenAI-compatible endpoints, set `llm_auth.base_url` to an API root like `http://host.docker.internal:7700/v1`.
- Configure agent tools through `agent_config.openhands.mcp_servers`; do not hardcode MCP servers in `AgentCore`.
- Filter OneBot inbound messages through `adapter_config.onebot.gateway` before forwarding them to the Core HTTP webhook.
- Put agent-authored reusable MCP plugins under `.agents/mcps/{name}/server.py`; use `agent_workspace/` or `tmp/` for scratch data.

### Testing guidance for new work
- Add new tests under a dedicated `tests/` directory.
- Prefer pytest naming: `tests/**/test_*.py`, `test_*` functions.
- For async logic, test happy path + failure path (timeouts, malformed response, empty result).

## 7) Agent Working Rules (Repo-specific)
- Make minimal, focused diffs; avoid opportunistic rewrites.
- Do not silently change config schema without updating templates/docs.
- If you add tooling (ruff/black/pytest config), document exact commands in this file.
- Prefer backward-compatible changes to bot event formats.
