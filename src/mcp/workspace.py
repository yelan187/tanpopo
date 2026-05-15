import os
import subprocess
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from src.runtime import global_config, register_logger


logger = register_logger("workspace-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-workspace")
MAX_OUTPUT_CHARS = 20000


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


@mcp.tool
def bash_tool(command: str, timeout: int = 60) -> dict[str, Any]:
    """Run a shell command in the workspace and return stdout/stderr."""
    clean_command = command.strip()
    if not clean_command:
        return {"ok": False, "error": "command is empty"}

    try:
        result = subprocess.run(
            clean_command,
            shell=True,
            executable=os.environ.get("SHELL", "/bin/sh"),
            cwd=_workspace_root(),
            text=True,
            capture_output=True,
            timeout=max(1, min(int(timeout), 300)),
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate(exc.stdout or "")
        stderr, stderr_truncated = _truncate(exc.stderr or "")
        return {
            "ok": False,
            "error": "command timed out",
            "stdout": stdout,
            "stderr": stderr,
            "truncated": stdout_truncated or stderr_truncated,
        }

    stdout, stdout_truncated = _truncate(result.stdout)
    stderr, stderr_truncated = _truncate(result.stderr)
    logger.info(f"bash_tool -> returncode={result.returncode} command={clean_command}")
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": stdout_truncated or stderr_truncated,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
