import json
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from src.runtime import global_config, register_logger
from src.runtime.registry import (
    append_history,
    load_mcp_servers,
    load_runtime_config,
    load_skill_settings,
    request_reload,
    save_mcp_servers,
    save_runtime_config,
    save_skill_settings,
)


logger = register_logger("plugin-manager-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-plugin-manager")
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
HOT_CONFIG_SCHEMA: dict[str, dict[str, set[str]]] = {
    "llm_auth": {"": {"api_key", "base_url"}},
    "agent_config": {
        "gateway": {
            "enabled",
            "allowed_sessions",
            "allowed_private_users",
            "allowed_groups",
            "allow_private_without_list",
        },
        "openhands": {"model", "system_prompt", "workspace"},
        "openhands.condenser": {
            "enabled",
            "max_size",
            "max_tokens",
            "keep_first",
            "minimum_progress",
            "hard_context_reset_max_retries",
            "hard_context_reset_context_scaling",
        },
    },
}


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not NAME_PATTERN.match(clean):
        raise ValueError("name must be 1-64 chars: letters, numbers, _ or -")
    return clean


def _skill_path(name: str) -> Path:
    return _workspace_root() / ".agents" / "skills" / name / "SKILL.md"


@mcp.tool
def list_skills() -> dict[str, Any]:
    """List skill registry entries and discovered skill files."""
    root = _workspace_root()
    settings = load_skill_settings(root)
    skills_dir = root / ".agents" / "skills"
    discovered = []
    if skills_dir.is_dir():
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            discovered.append(path.parent.name)
    return {"ok": True, "settings": settings, "discovered": discovered}


@mcp.tool
def add_skill(name: str, content: str, enabled: bool = True) -> dict[str, Any]:
    """Create or replace a project skill under .agents/skills/{name}/SKILL.md."""
    try:
        clean_name = _validate_name(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    skill_path = _skill_path(clean_name)
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(_normalize_skill_content(clean_name, content), encoding="utf-8")

    settings = load_skill_settings(_workspace_root())
    settings[clean_name] = {"enabled": bool(enabled)}
    save_skill_settings(settings, _workspace_root())
    append_history(
        "add_skill",
        {"name": clean_name, "enabled": bool(enabled), "path": str(skill_path)},
        _workspace_root(),
    )
    request_reload(f"skill {clean_name} added", _workspace_root())
    return {"ok": True, "name": clean_name, "path": str(skill_path)}


@mcp.tool
def set_skill_enabled(name: str, enabled: bool) -> dict[str, Any]:
    """Enable or disable a skill by name."""
    try:
        clean_name = _validate_name(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    settings = load_skill_settings(_workspace_root())
    current = settings.get(clean_name, {})
    current["enabled"] = bool(enabled)
    settings[clean_name] = current
    save_skill_settings(settings, _workspace_root())
    append_history(
        "set_skill_enabled",
        {"name": clean_name, "enabled": bool(enabled)},
        _workspace_root(),
    )
    request_reload(f"skill {clean_name} enabled={bool(enabled)}", _workspace_root())
    return {"ok": True, "name": clean_name, "enabled": bool(enabled)}


@mcp.tool
def list_mcp_servers() -> dict[str, Any]:
    """List MCP server registry entries."""
    return {"ok": True, "servers": load_mcp_servers(_workspace_root())}


@mcp.tool
def add_mcp_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    enabled: bool = True,
    transport: str = "stdio",
    cwd: str = ".",
    description: str = "",
) -> dict[str, Any]:
    """Add or replace an MCP server registry entry."""
    try:
        clean_name = _validate_name(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    servers = load_mcp_servers(_workspace_root())
    servers[clean_name] = {
        "enabled": bool(enabled),
        "transport": transport.strip() or "stdio",
        "command": command.strip(),
        "args": [str(item) for item in args or []],
        "cwd": cwd.strip() or ".",
        "env": {},
        "description": description.strip(),
    }
    save_mcp_servers(servers, _workspace_root())
    append_history(
        "add_mcp_server",
        {"name": clean_name, "enabled": bool(enabled), "args": args or []},
        _workspace_root(),
    )
    request_reload(f"mcp {clean_name} added", _workspace_root())
    return {"ok": True, "name": clean_name, "server": servers[clean_name]}


@mcp.tool
def set_mcp_enabled(name: str, enabled: bool) -> dict[str, Any]:
    """Enable or disable an MCP server by name."""
    try:
        clean_name = _validate_name(name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    servers = load_mcp_servers(_workspace_root())
    if clean_name not in servers:
        return {"ok": False, "error": f"unknown MCP server: {clean_name}"}
    servers[clean_name]["enabled"] = bool(enabled)
    save_mcp_servers(servers, _workspace_root())
    append_history(
        "set_mcp_enabled",
        {"name": clean_name, "enabled": bool(enabled)},
        _workspace_root(),
    )
    request_reload(f"mcp {clean_name} enabled={bool(enabled)}", _workspace_root())
    return {"ok": True, "name": clean_name, "enabled": bool(enabled)}


@mcp.tool
def get_runtime_config() -> dict[str, Any]:
    """Return hot-reloadable runtime config overrides."""
    return {"ok": True, "config": load_runtime_config(_workspace_root())}


@mcp.tool
def update_runtime_config(
    config_json: str, merge: bool = True, reload: bool = True
) -> dict[str, Any]:
    """Update hot-reloadable runtime config overrides from a JSON object."""
    try:
        parsed = json.loads(config_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid config_json: {exc}"}
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "config_json must decode to an object"}

    try:
        sanitized = _sanitize_runtime_config(parsed)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    root = _workspace_root()
    current = load_runtime_config(root) if merge else {}
    updated = _deep_merge(current, sanitized) if merge else sanitized
    save_runtime_config(updated, root)
    append_history("update_runtime_config", {"config": sanitized}, root)
    reload_request = None
    if reload:
        reload_request = request_reload("runtime config changed", root)
    return {"ok": True, "config": updated, "reload_request": reload_request}


@mcp.tool
def clear_runtime_config(reload: bool = True) -> dict[str, Any]:
    """Clear all hot-reloadable runtime config overrides."""
    root = _workspace_root()
    save_runtime_config({}, root)
    append_history("clear_runtime_config", {}, root)
    reload_request = None
    if reload:
        reload_request = request_reload("runtime config cleared", root)
    return {"ok": True, "config": {}, "reload_request": reload_request}


@mcp.tool
def request_agent_reload(reason: str = "plugin registry changed") -> dict[str, Any]:
    """Ask AgentCore to rebuild its Agent and conversations on the next message."""
    payload = request_reload(reason.strip() or "plugin registry changed", _workspace_root())
    return {"ok": True, "reload_request": payload}


def _normalize_skill_content(name: str, content: str) -> str:
    text = content.strip()
    if text.startswith("---"):
        return f"{text}\n"
    return (
        "---\n"
        f"name: {name}\n"
        f"description: Runtime skill {name}.\n"
        "---\n\n"
        f"{text}\n"
    )


def _sanitize_runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for section, value in config.items():
        if section == "llm_auth":
            if not isinstance(value, dict):
                raise ValueError("llm_auth must be an object")
            allowed = HOT_CONFIG_SCHEMA["llm_auth"][""]
            result[section] = _filter_keys(value, allowed, "llm_auth")
            continue

        if section == "agent_config":
            if not isinstance(value, dict):
                raise ValueError("agent_config must be an object")
            agent_config: dict[str, Any] = {}
            for subsection, subsection_value in value.items():
                if subsection == "openhands":
                    if not isinstance(subsection_value, dict):
                        raise ValueError("agent_config.openhands must be an object")
                    agent_config[subsection] = _sanitize_openhands_config(
                        subsection_value
                    )
                    continue

                if subsection not in HOT_CONFIG_SCHEMA["agent_config"]:
                    raise ValueError(f"unsupported hot config section: agent_config.{subsection}")
                if not isinstance(subsection_value, dict):
                    raise ValueError(f"agent_config.{subsection} must be an object")
                agent_config[subsection] = _filter_keys(
                    subsection_value,
                    HOT_CONFIG_SCHEMA["agent_config"][subsection],
                    f"agent_config.{subsection}",
                )
            result[section] = agent_config
            continue

        raise ValueError(f"unsupported hot config section: {section}")
    return result


def _filter_keys(value: dict[str, Any], allowed: set[str], path: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key not in allowed:
            raise ValueError(f"unsupported hot config key: {path}.{key}")
        result[str(key)] = item
    return result


def _sanitize_openhands_config(value: dict[str, Any]) -> dict[str, Any]:
    allowed = HOT_CONFIG_SCHEMA["agent_config"]["openhands"]
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "condenser":
            if not isinstance(item, dict):
                raise ValueError("agent_config.openhands.condenser must be an object")
            result[key] = _filter_keys(
                item,
                HOT_CONFIG_SCHEMA["agent_config"]["openhands.condenser"],
                "agent_config.openhands.condenser",
            )
            continue
        if key not in allowed:
            raise ValueError(f"unsupported hot config key: agent_config.openhands.{key}")
        result[str(key)] = item
    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
