import os
import sys
from pathlib import Path
from typing import Any

from .registry import load_mcp_servers


def build_mcp_config(
    agent_config: dict[str, Any],
    workspace_root: Path,
    http_settings: dict[str, Any] | None = None,
    core_settings: dict[str, Any] | None = None,
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
            name,
            server_config,
            workspace_root,
            http_settings or {},
            core_settings or {},
        )
        if normalized is not None:
            servers[str(name)] = normalized

    return {"mcpServers": servers}


def _normalize_server_config(
    name: str,
    server_config: dict[str, Any],
    workspace_root: Path,
    http_settings: dict[str, Any],
    core_settings: dict[str, Any],
) -> dict[str, Any] | None:
    command = str(server_config.get("command", "")).strip()
    if not command:
        command = "mcp-server-fetch" if name == "fetch" else sys.executable
    if not command:
        return None

    args = server_config.get("args", [])
    if not isinstance(args, list):
        args = []
    if name == "qqio" and not args:
        args = ["-m", "src.mcp.qqio"]
    if name == "fetch" and not args:
        args = ["--ignore-robots-txt"]
    if name == "capability" and not args:
        args = ["-m", "src.mcp.capability"]
    if name == "context" and not args:
        args = ["-m", "src.mcp.context"]
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
    normalized_env.update(_shared_env(normalized_env, workspace_root))
    if name == "qqio":
        normalized_env.update(_qqio_env(workspace_root, normalized_env, http_settings))
    if name == "context":
        normalized_env.update(_context_env(normalized_env, core_settings))

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


def _shared_env(existing_env: dict[str, str], workspace_root: Path) -> dict[str, str]:
    return {
        "PYTHONPATH": existing_env.get(
            "PYTHONPATH",
            os.getenv("PYTHONPATH", str(workspace_root)),
        ),
        "FASTMCP_SHOW_SERVER_BANNER": existing_env.get(
            "FASTMCP_SHOW_SERVER_BANNER",
            os.getenv("FASTMCP_SHOW_SERVER_BANNER", "false"),
        ),
        "FASTMCP_LOG_LEVEL": existing_env.get(
            "FASTMCP_LOG_LEVEL",
            os.getenv("FASTMCP_LOG_LEVEL", "ERROR"),
        ),
        "LITELLM_LOG": existing_env.get(
            "LITELLM_LOG",
            os.getenv("LITELLM_LOG", "ERROR"),
        ),
        "LITELLM_LOCAL_MODEL_COST_MAP": existing_env.get(
            "LITELLM_LOCAL_MODEL_COST_MAP",
            os.getenv("LITELLM_LOCAL_MODEL_COST_MAP", "True"),
        ),
        "OPENHANDS_SUPPRESS_BANNER": existing_env.get(
            "OPENHANDS_SUPPRESS_BANNER",
            os.getenv("OPENHANDS_SUPPRESS_BANNER", "1"),
        ),
    }


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


def _context_env(
    existing_env: dict[str, str], core_settings: dict[str, Any]
) -> dict[str, str]:
    host = str(core_settings.get("adapter_host", "")).strip()
    if not host:
        bind_host = str(core_settings.get("host", "127.0.0.1")).strip()
        host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
    port = str(core_settings.get("port", "8080")).strip() or "8080"
    return {
        "TANPOPO_CORE_URL": existing_env.get(
            "TANPOPO_CORE_URL",
            os.getenv("TANPOPO_CORE_URL", f"http://{host}:{port}"),
        ),
    }
