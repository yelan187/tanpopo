from pathlib import Path
from typing import Any

import yaml
from fastmcp import FastMCP

from src.runtime import global_config, register_logger
from src.runtime.mcp import build_mcp_config
from src.runtime.registry import load_runtime_registry, load_skill_settings, runtime_paths


logger = register_logger("capability-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-capability")


def _workspace_root() -> Path:
    return Path.cwd().resolve()


@mcp.tool
def runtime_capabilities() -> dict[str, Any]:
    """List enabled MCP servers, discovered skills, and runtime registry paths."""
    root = _workspace_root()
    mcp_config = build_mcp_config(
        global_config.agent_config,
        root,
        global_config.http_settings,
        global_config.core_settings,
    )
    skills = _discover_skills(root)
    paths = runtime_paths(root)
    return {
        "ok": True,
        "mcp_servers": sorted(mcp_config.get("mcpServers", {}).keys()),
        "skills": skills,
        "paths": {
            "runtime_dir": str(paths.runtime_dir),
            "mcp_registry": str(paths.mcp_registry),
            "skill_registry": str(paths.skill_registry),
            "runtime_config": str(paths.runtime_config),
            "history": str(paths.history),
            "reload_request": str(paths.reload_request),
        },
    }


@mcp.tool
def runtime_registry() -> dict[str, Any]:
    """Return the raw runtime registry for MCP and skill plugin state."""
    return {"ok": True, "registry": load_runtime_registry(_workspace_root())}


def _discover_skills(root: Path) -> list[dict[str, Any]]:
    skills_dir = root / ".agents" / "skills"
    settings = load_skill_settings(root)
    if not skills_dir.is_dir():
        return []

    discovered = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        metadata = _read_skill_metadata(path)
        name = str(metadata.get("name") or path.parent.name).strip() or path.parent.name
        skill_setting = settings.get(name, {})
        discovered.append(
            {
                "name": name,
                "enabled": bool(skill_setting.get("enabled", True)),
                "description": str(metadata.get("description") or ""),
                "source": str(path),
            }
        )
    return discovered


def _read_skill_metadata(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"读取 skill 失败[{path}]: {exc}")
        return {}

    if not text.startswith("---"):
        return {}

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"解析 skill 元数据失败[{path}]: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    mcp.run(transport="stdio")
