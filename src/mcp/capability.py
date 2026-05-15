from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from openhands.sdk.skills import load_skills_from_dir

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

    try:
        repo_skills, knowledge_skills, agent_skills = load_skills_from_dir(skills_dir)
    except Exception as exc:
        logger.warning(f"发现 skills 失败: {exc}")
        return []

    discovered = []
    for skill in [*repo_skills.values(), *knowledge_skills.values(), *agent_skills.values()]:
        skill_setting = settings.get(skill.name, {})
        discovered.append(
            {
                "name": skill.name,
                "enabled": bool(skill_setting.get("enabled", True)),
                "description": skill.description,
                "source": skill.source,
            }
        )
    return discovered


if __name__ == "__main__":
    mcp.run(transport="stdio")
