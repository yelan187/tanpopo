import os
import re
import subprocess
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from src.runtime import global_config, register_logger


logger = register_logger("git-ops-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-git-ops")
MAX_OUTPUT_CHARS = 20000
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _allowed_roots() -> list[Path]:
    raw_paths = os.getenv(
        "TANPOPO_GIT_ALLOWED_PATHS", ".agents/skills,.agents/mcps"
    )
    root = _workspace_root()
    result = []
    for item in raw_paths.split(","):
        clean = item.strip()
        if not clean:
            continue
        candidate = (root / clean).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        result.append(candidate)
    return result or [root / ".agents" / "skills", root / ".agents" / "mcps"]


def _run_git(args: list[str], timeout: int = 60) -> dict[str, Any]:
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=_workspace_root(),
            text=True,
            capture_output=True,
            timeout=max(1, min(int(timeout), 300)),
        )
    except FileNotFoundError:
        return {"ok": False, "error": "git is not installed"}
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate(exc.stdout or "")
        stderr, stderr_truncated = _truncate(exc.stderr or "")
        return {
            "ok": False,
            "error": "git command timed out",
            "stdout": stdout,
            "stderr": stderr,
            "truncated": stdout_truncated or stderr_truncated,
        }

    stdout, stdout_truncated = _truncate(result.stdout)
    stderr, stderr_truncated = _truncate(result.stderr)
    logger.info(f"git_ops -> returncode={result.returncode} args={args}")
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": stdout_truncated or stderr_truncated,
    }


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _clean_path(path: str) -> str:
    clean = path.strip().lstrip("/")
    if not clean or clean == ".":
        raise ValueError("path is empty")
    if any(part in {"", ".", ".."} for part in Path(clean).parts):
        raise ValueError(f"unsafe path: {path}")
    return clean


def _validate_allowed_paths(paths: list[str] | None) -> tuple[bool, str, list[str]]:
    requested = paths or [".agents/skills", ".agents/mcps"]
    root = _workspace_root()
    allowed_roots = _allowed_roots()
    clean_paths = []
    for path in requested:
        try:
            clean = _clean_path(str(path))
        except ValueError as exc:
            return False, str(exc), []
        resolved = (root / clean).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return False, f"path escapes workspace: {path}", []
        if not any(
            resolved == allowed_root or resolved.is_relative_to(allowed_root)
            for allowed_root in allowed_roots
        ):
            allowed = [str(item.relative_to(root)) for item in allowed_roots]
            return False, f"path not allowed: {path}; allowed roots: {allowed}", []
        clean_paths.append(clean)
    return True, "", clean_paths


def _current_branch() -> str:
    result = _run_git(["branch", "--show-current"], timeout=10)
    if not result.get("ok"):
        return ""
    return str(result.get("stdout") or "").strip()


def _validate_branch_name(branch_name: str) -> str:
    clean = branch_name.strip()
    if not clean:
        raise ValueError("branch_name is empty")
    if clean.startswith("-") or ".." in clean or clean.endswith(".lock"):
        raise ValueError("branch_name is unsafe")
    if not BRANCH_PATTERN.match(clean):
        raise ValueError("branch_name contains unsupported characters")
    return clean


@mcp.tool
def git_status() -> dict[str, Any]:
    """Return short git status and current branch."""
    status = _run_git(["status", "--short", "--branch"], timeout=20)
    status["branch"] = _current_branch()
    status["allowed_paths"] = [
        str(path.relative_to(_workspace_root())) for path in _allowed_roots()
    ]
    return status


@mcp.tool
def git_create_branch(branch_name: str, checkout: bool = True) -> dict[str, Any]:
    """Create a self-evolution branch. Use this before committing Bot changes."""
    try:
        clean_branch = _validate_branch_name(branch_name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    args = ["switch", "-c", clean_branch] if checkout else ["branch", clean_branch]
    return _run_git(args, timeout=30)


@mcp.tool
def git_diff(paths: list[str] | None = None) -> dict[str, Any]:
    """Show diff for allowed self-evolution paths."""
    ok, error, clean_paths = _validate_allowed_paths(paths)
    if not ok:
        return {"ok": False, "error": error}
    return _run_git(["diff", "--", *clean_paths], timeout=30)


@mcp.tool
def git_commit_allowed(paths: list[str] | None, message: str) -> dict[str, Any]:
    """Stage and commit allowed MCP/skill changes only."""
    clean_message = message.strip()
    if not clean_message:
        return {"ok": False, "error": "message is empty"}

    ok, error, clean_paths = _validate_allowed_paths(paths)
    if not ok:
        return {"ok": False, "error": error}

    add_result = _run_git(["add", "--", *clean_paths], timeout=30)
    if not add_result.get("ok"):
        return {"ok": False, "stage": add_result}

    diff_result = _run_git(["diff", "--cached", "--quiet", "--", *clean_paths])
    if diff_result.get("ok"):
        return {"ok": False, "error": "no staged changes in allowed paths"}

    commit_result = _run_git(["commit", "-m", clean_message], timeout=120)
    return {"ok": bool(commit_result.get("ok")), "commit": commit_result}


@mcp.tool
def git_push_current_branch(remote: str = "origin") -> dict[str, Any]:
    """Push the current branch to a git remote."""
    clean_remote = remote.strip() or "origin"
    if clean_remote.startswith("-") or "/" in clean_remote:
        return {"ok": False, "error": "remote name is unsafe"}

    branch = _current_branch()
    if not branch:
        return {"ok": False, "error": "not on a branch"}
    if branch in {"main", "master"}:
        return {"ok": False, "error": "refusing to push directly from main/master"}

    return _run_git(["push", "-u", clean_remote, branch], timeout=300)


if __name__ == "__main__":
    mcp.run(transport="stdio")
