import os
import sys
from pathlib import Path
from typing import Any

from .registry import load_mcp_servers


def build_mcp_config(
    agent_config: dict[str, Any],
    workspace_root: Path,
    http_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    openhands_config = agent_config.get("openhands", {})
    configured_servers = openhands_config.get("mcp_servers")
    server_configs = load_mcp_servers(workspace_root)
    if isinstance(configured_servers, dict):
        for name, config in configured_servers.items():
            if not isinstance(config, dict):
                continue
            server_name = str(name)
            existing = server_configs.get(server_name, {})
            server_configs[server_name] = _deep_merge(existing, config)

    servers: dict[str, dict[str, Any]] = {}
    for name, server_config in server_configs.items():
        if not isinstance(server_config, dict):
            continue
        normalized = _normalize_server_config(
            name, server_config, workspace_root, http_settings or {}
        )
        if normalized is not None:
            servers[str(name)] = normalized

    return {"mcpServers": servers}


def _normalize_server_config(
    name: str,
    server_config: dict[str, Any],
    workspace_root: Path,
    http_settings: dict[str, Any],
) -> dict[str, Any] | None:
    command = str(server_config.get("command", "")).strip()
    if not command:
        command = sys.executable
    if not command:
        return None

    args = server_config.get("args", [])
    if not isinstance(args, list):
        args = []
    if name == "qqio" and not args:
        args = ["-m", "src.mcp.qqio"]
    if name == "fetch" and not args:
        args = ["mcp-server-fetch"]
    if name == "capability" and not args:
        args = ["-m", "src.mcp.capability"]
    if name == "plugin_manager" and not args:
        args = ["-m", "src.mcp.plugin_manager"]
    if name == "workspace" and not args:
        args = ["-m", "src.mcp.workspace"]

    enabled = server_config.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() not in {"0", "false", "no", "off"}
    if not bool(enabled):
        return None

    cwd = str(server_config.get("cwd", "")).strip() or str(workspace_root)
    if cwd == ".":
        cwd = str(workspace_root)

    env = server_config.get("env", {})
    normalized_env = (
        {str(key): str(value) for key, value in env.items()}
        if isinstance(env, dict)
        else {}
    )
    if name == "qqio":
        normalized_env.update(_qqio_env(workspace_root, normalized_env, http_settings))

    return {
        "transport": str(server_config.get("transport", "stdio")).strip() or "stdio",
        "command": command,
        "args": [str(item) for item in args],
        "cwd": cwd,
        "env": normalized_env,
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _qqio_env(
    workspace_root: Path,
    existing_env: dict[str, str],
    http_settings: dict[str, Any],
) -> dict[str, str]:
    return {
        "TANPOPO_HTTP_HOST": existing_env.get(
            "TANPOPO_HTTP_HOST",
            os.getenv("TANPOPO_HTTP_HOST", str(http_settings.get("host", "127.0.0.1"))),
        ),
        "TANPOPO_HTTP_PORT": existing_env.get(
            "TANPOPO_HTTP_PORT",
            os.getenv("TANPOPO_HTTP_PORT", str(http_settings.get("port", 3000))),
        ),
        "TANPOPO_MEMORY_FILE": existing_env.get(
            "TANPOPO_MEMORY_FILE",
            str(workspace_root / "tmp" / "agent_memories.jsonl"),
        ),
    }
