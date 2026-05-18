import json
import os
from typing import Any
from urllib import error, parse, request

from fastmcp import FastMCP


mcp = FastMCP("tanpopo-context")


def _core_url() -> str:
    return os.getenv("TANPOPO_CORE_URL", "http://127.0.0.1:8080").rstrip("/")


def _call_core(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(
        f"{_core_url()}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        return {
            "ok": False,
            "error": f"http error {exc.code}",
            "detail": exc.read().decode("utf-8", errors="ignore"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not raw:
        return {"ok": True}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "raw": raw}
    return parsed if isinstance(parsed, dict) else {"ok": True, "data": parsed}


@mcp.tool
def context_list() -> dict[str, Any]:
    """List active short-term contexts in Tanpopo Core."""
    return _call_core("GET", "/v1/contexts")


@mcp.tool
def context_close(context_id: str) -> dict[str, Any]:
    """Close one short-term context and drop its buffered events/conversation."""
    clean_context_id = context_id.strip()
    if not clean_context_id:
        return {"ok": False, "error": "context_id is empty"}
    quoted = parse.quote(clean_context_id, safe="")
    return _call_core("DELETE", f"/v1/contexts/{quoted}")


@mcp.tool
def context_reset(context_id: str) -> dict[str, Any]:
    """Reset one short-term context. This keeps long-term memories untouched."""
    clean_context_id = context_id.strip()
    if not clean_context_id:
        return {"ok": False, "error": "context_id is empty"}
    quoted = parse.quote(clean_context_id, safe="")
    return _call_core("POST", f"/v1/contexts/{quoted}/reset", {})


if __name__ == "__main__":
    mcp.run(transport="stdio")
