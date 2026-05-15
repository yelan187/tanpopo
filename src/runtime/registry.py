import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


RUNTIME_DIR_NAME = ".agent_runtime"
MCP_REGISTRY_FILE = "mcps.yaml"
SKILL_REGISTRY_FILE = "skills.yaml"
RUNTIME_CONFIG_FILE = "config.yaml"
HISTORY_FILE = "history.jsonl"
RELOAD_REQUEST_FILE = "reload_request.json"


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    runtime_dir: Path
    mcp_registry: Path
    skill_registry: Path
    runtime_config: Path
    history: Path
    reload_request: Path


def runtime_paths(workspace_root: Path | str | None = None) -> RuntimePaths:
    root = Path(workspace_root or Path.cwd()).resolve()
    runtime_dir = root / RUNTIME_DIR_NAME
    return RuntimePaths(
        root=root,
        runtime_dir=runtime_dir,
        mcp_registry=runtime_dir / MCP_REGISTRY_FILE,
        skill_registry=runtime_dir / SKILL_REGISTRY_FILE,
        runtime_config=runtime_dir / RUNTIME_CONFIG_FILE,
        history=runtime_dir / HISTORY_FILE,
        reload_request=runtime_dir / RELOAD_REQUEST_FILE,
    )


def default_mcp_registry() -> dict[str, Any]:
    return {
        "servers": {
            "qqio": {
                "enabled": True,
                "transport": "stdio",
                "command": "",
                "args": ["-m", "src.mcp.qqio"],
                "cwd": ".",
                "env": {},
                "description": "QQ/OneBot messaging and common query tools.",
            },
            "fetch": {
                "enabled": True,
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-server-fetch", "--ignore-robots-txt"],
                "cwd": ".",
                "env": {
                    "PYTHONIOENCODING": "utf-8",
                },
                "description": "Official fetch MCP server for retrieving webpages as markdown.",
            },
            "filesystem": {
                "enabled": True,
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"],
                "cwd": ".",
                "env": {},
                "description": "Official filesystem MCP server with full container filesystem access.",
            },
            "workspace": {
                "enabled": True,
                "transport": "stdio",
                "command": "",
                "args": ["-m", "src.mcp.workspace"],
                "cwd": ".",
                "env": {},
                "description": "Local bash command tool.",
            },
            "capability": {
                "enabled": True,
                "transport": "stdio",
                "command": "",
                "args": ["-m", "src.mcp.capability"],
                "cwd": ".",
                "env": {},
                "description": "Inspect enabled MCPs, skills, and runtime state.",
            },
            "plugin_manager": {
                "enabled": True,
                "transport": "stdio",
                "command": "",
                "args": ["-m", "src.mcp.plugin_manager"],
                "cwd": ".",
                "env": {},
                "description": "Manage skill and MCP runtime registry entries.",
            },
        }
    }


def default_skill_registry() -> dict[str, Any]:
    return {"skills": {}}


def default_runtime_config() -> dict[str, Any]:
    return {
        "llm_auth": {},
        "agent_config": {
            "gateway": {},
            "openhands": {},
        },
    }


def load_runtime_registry(workspace_root: Path | str | None = None) -> dict[str, Any]:
    paths = runtime_paths(workspace_root)
    mcps = _load_yaml(paths.mcp_registry, default_mcp_registry())
    skills = _load_yaml(paths.skill_registry, default_skill_registry())
    config = _load_yaml(paths.runtime_config, default_runtime_config())
    return {"mcps": mcps, "skills": skills, "config": config}


def load_mcp_servers(workspace_root: Path | str | None = None) -> dict[str, dict[str, Any]]:
    registry = _load_yaml(runtime_paths(workspace_root).mcp_registry, default_mcp_registry())
    servers = registry.get("servers", {})
    if not isinstance(servers, dict):
        return {}
    return {str(name): config for name, config in servers.items() if isinstance(config, dict)}


def load_skill_settings(workspace_root: Path | str | None = None) -> dict[str, dict[str, Any]]:
    registry = _load_yaml(
        runtime_paths(workspace_root).skill_registry, default_skill_registry()
    )
    skills = registry.get("skills", {})
    if not isinstance(skills, dict):
        return {}
    return {str(name): config for name, config in skills.items() if isinstance(config, dict)}


def load_runtime_config(workspace_root: Path | str | None = None) -> dict[str, Any]:
    return _load_yaml(runtime_paths(workspace_root).runtime_config, default_runtime_config())


def save_mcp_servers(
    servers: dict[str, dict[str, Any]], workspace_root: Path | str | None = None
) -> None:
    _write_yaml(runtime_paths(workspace_root).mcp_registry, {"servers": servers})


def save_skill_settings(
    skills: dict[str, dict[str, Any]], workspace_root: Path | str | None = None
) -> None:
    _write_yaml(runtime_paths(workspace_root).skill_registry, {"skills": skills})


def save_runtime_config(
    config: dict[str, Any], workspace_root: Path | str | None = None
) -> None:
    _write_yaml(runtime_paths(workspace_root).runtime_config, config)


def append_history(
    action: str,
    detail: dict[str, Any],
    workspace_root: Path | str | None = None,
) -> None:
    paths = runtime_paths(workspace_root)
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    item = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "detail": detail,
    }
    with paths.history.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(item, ensure_ascii=False))
        fp.write("\n")


def request_reload(
    reason: str,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    paths = runtime_paths(workspace_root)
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_at": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
    }
    paths.reload_request.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    append_history("request_reload", payload, workspace_root)
    return payload


def reload_request_mtime(workspace_root: Path | str | None = None) -> float:
    path = runtime_paths(workspace_root).reload_request
    if not path.exists():
        return 0.0
    return path.stat().st_mtime


def _load_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return default
    return data if isinstance(data, dict) else default


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
