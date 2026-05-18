import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from fastmcp import FastMCP

from src.event import MessageEvent
from src.runtime import global_config, register_logger


logger = register_logger("qqio-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-qqio")


def _onebot_api_url(action: str) -> str:
    host = os.getenv("TANPOPO_HTTP_HOST") or str(
        global_config.http_settings.get("host", "127.0.0.1")
    )
    port = os.getenv("TANPOPO_HTTP_PORT") or str(
        global_config.http_settings.get("port", 3000)
    )
    return f"http://{host}:{port}/{action}"


def _post_onebot(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        _onebot_api_url(action),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        return {
            "ok": False,
            "error": f"http error {exc.code}",
            "detail": exc.read().decode("utf-8", errors="ignore"),
            "action": action,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "action": action}

    if not raw:
        return {"ok": True, "action": action, "data": None}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "action": action, "raw": raw}

    if isinstance(parsed, dict):
        status = parsed.get("status")
        retcode = parsed.get("retcode")
        parsed["ok"] = status == "ok" and retcode in (0, None)
        parsed.setdefault("action", action)
        return parsed

    return {"ok": True, "action": action, "data": parsed}


def _memory_path() -> Path:
    memory_file = os.getenv("TANPOPO_MEMORY_FILE")
    if memory_file:
        return Path(memory_file)
    return Path.cwd() / "tmp" / "agent_memories.jsonl"


def _normalize_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, list):
        return [str(item).strip() for item in tags if str(item).strip()]

    text = str(tags).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def _message_target(
    message_type: str, group_id: int | None, user_id: int | None
) -> dict[str, int]:
    if message_type == "group":
        if group_id is None:
            raise ValueError("group_id is required for group message")
        return {"group_id": int(group_id)}
    if message_type == "private":
        if user_id is None:
            raise ValueError("user_id is required for private message")
        return {"user_id": int(user_id)}
    raise ValueError("message_type must be group/private")


@mcp.tool
def qq_send_text(
    message_type: str,
    text: str,
    group_id: int | None = None,
    user_id: int | None = None,
    reply_to_message_id: int | None = None,
    at_user_id: int | None = None,
    auto_escape: bool = False,
) -> dict[str, Any]:
    """Send a text message to a group or private chat."""
    clean_text = text.strip()
    if not clean_text:
        return {"ok": False, "error": "text is empty"}

    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    message: list[dict[str, Any]] = []
    if reply_to_message_id is not None:
        message.append({"type": "reply", "data": {"id": str(reply_to_message_id)}})
    if at_user_id is not None and message_type == "group":
        message.append({"type": "at", "data": {"qq": str(at_user_id)}})
        clean_text = f" {clean_text}"
    message.append({"type": "text", "data": {"text": clean_text}})

    params: dict[str, Any] = {
        "message_type": message_type,
        "message": message,
        "auto_escape": bool(auto_escape),
    }
    params.update(target)
    result = _post_onebot("send_msg", params)
    logger.info(f"qqio发送文本 -> {json.dumps(message, ensure_ascii=False)}")
    return result


@mcp.tool
def qq_send_face(
    message_type: str,
    face_id: int,
    group_id: int | None = None,
    user_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> dict[str, Any]:
    """Send a QQ face/emoticon segment by OneBot face id."""
    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    clean_face_id = str(int(face_id))
    message: list[dict[str, Any]] = []
    if reply_to_message_id is not None:
        message.append({"type": "reply", "data": {"id": str(reply_to_message_id)}})
    message.append({"type": "face", "data": {"id": clean_face_id}})

    params: dict[str, Any] = {"message_type": message_type, "message": message}
    params.update(target)
    result = _post_onebot("send_msg", params)
    logger.info(f"qqio发送表情 -> {json.dumps(message, ensure_ascii=False)}")
    return result


@mcp.tool
def qq_send_image(
    message_type: str,
    file: str,
    group_id: int | None = None,
    user_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> dict[str, Any]:
    """Send an image segment. `file` supports path, URL, or base64:// content."""
    clean_file = file.strip()
    if not clean_file:
        return {"ok": False, "error": "file is empty"}

    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    message: list[dict[str, Any]] = []
    if reply_to_message_id is not None:
        message.append({"type": "reply", "data": {"id": str(reply_to_message_id)}})
    message.append({"type": "image", "data": {"file": clean_file}})

    params: dict[str, Any] = {"message_type": message_type, "message": message}
    params.update(target)
    return _post_onebot("send_msg", params)


@mcp.tool
def qq_get_msg(message_id: int) -> dict[str, Any]:
    """Get message detail by message_id."""
    return _post_onebot("get_msg", {"message_id": int(message_id)})


@mcp.tool
def qq_get_group_msg_history(
    group_id: int, message_seq: int = 0, count: int = 20
) -> dict[str, Any]:
    """Get recent group message history. message_seq=0 means latest on many builds."""
    return _post_onebot(
        "get_group_msg_history",
        {
            "group_id": int(group_id),
            "message_seq": int(message_seq),
            "count": max(1, min(int(count), 50)),
        },
    )


@mcp.tool
def qq_get_friend_msg_history(
    user_id: int, message_seq: int = 0, count: int = 20
) -> dict[str, Any]:
    """Get recent private message history."""
    return _post_onebot(
        "get_friend_msg_history",
        {
            "user_id": int(user_id),
            "message_seq": int(message_seq),
            "count": max(1, min(int(count), 50)),
        },
    )


@mcp.tool
def qq_get_login_info() -> dict[str, Any]:
    """Get bot account information."""
    return _post_onebot("get_login_info", {})


@mcp.tool
def qq_get_group_list() -> dict[str, Any]:
    """Get the group list."""
    return _post_onebot("get_group_list", {})


@mcp.tool
def qq_get_group_info(group_id: int, no_cache: bool = False) -> dict[str, Any]:
    """Get group information by group_id."""
    return _post_onebot(
        "get_group_info", {"group_id": int(group_id), "no_cache": no_cache}
    )


@mcp.tool
def qq_get_group_member_info(
    group_id: int, user_id: int, no_cache: bool = False
) -> dict[str, Any]:
    """Get member information in a group."""
    return _post_onebot(
        "get_group_member_info",
        {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "no_cache": no_cache,
        },
    )


@mcp.tool
def qq_get_group_member_list(group_id: int, no_cache: bool = False) -> dict[str, Any]:
    """Get members in a group."""
    return _post_onebot(
        "get_group_member_list", {"group_id": int(group_id), "no_cache": no_cache}
    )


@mcp.tool
def qq_call_api(action: str, params_json: str = "{}") -> dict[str, Any]:
    """Call a OneBot API by raw action and JSON params when no wrapper exists."""
    try:
        params = json.loads(params_json) if params_json.strip() else {}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid params_json: {exc}"}
    if not isinstance(params, dict):
        return {"ok": False, "error": "params_json must decode to an object"}
    return _post_onebot(action, params)


@mcp.tool
def qq_parse_message_event(event_json: str) -> dict[str, Any]:
    """Parse OneBot message event JSON with segment details."""
    try:
        payload = json.loads(event_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid json: {exc}"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "event_json must decode to an object"}

    message_event = MessageEvent(payload)
    segments: list[dict[str, Any]] = []
    for segment in message_event.message.segments:
        detail = {
            "type": segment.type,
            "data": segment.data,
            "as_text": message_event._segment_to_plaintext(
                segment, with_at=True, loop=False
            ),
        }
        if segment.type == "at":
            qq = segment.data.get("qq")
            detail["target"] = "all" if qq == "all" else str(qq)
        elif segment.type == "reply":
            detail["reply_message_id"] = segment.data.get("id")
        elif segment.type == "image":
            detail["file"] = segment.data.get("file")
            detail["url"] = segment.data.get("url")
        segments.append(detail)

    return {
        "ok": True,
        "parsed": {
            "message_type": message_event.message_type,
            "sub_type": message_event.sub_type,
            "message_id": message_event.message_id,
            "group_id": message_event.group_id,
            "user_id": message_event.user_id,
            "raw_message": message_event.raw_message,
            "plaintext": message_event.get_plaintext(with_at=True),
            "plaintext_without_at": message_event.get_plaintext(with_at=False),
            "at_list": message_event.at_list,
            "is_tome": message_event.is_tome,
            "sender": {
                "user_id": message_event.sender.user_id,
                "nickname": message_event.sender.nickname,
                "card": message_event.sender.card,
                "role": message_event.sender.role,
                "title": message_event.sender.title,
            },
            "segments": segments,
        },
    }


@mcp.tool
def memory_append(
    session_id: str, note: str, tags: list[str] | str | None = None
) -> dict[str, Any]:
    """Append one memory note to local JSONL storage."""
    clean_note = note.strip()
    if not clean_note:
        return {"ok": False, "error": "note is empty"}

    memory_path = _memory_path()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "session_id": session_id,
        "note": clean_note,
        "tags": _normalize_tags(tags),
    }
    with memory_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(item, ensure_ascii=False))
        fp.write("\n")
    return {"ok": True, "saved": True, "path": str(memory_path)}


@mcp.tool
def memory_search(session_id: str, query: str = "", limit: int = 5) -> dict[str, Any]:
    """Search notes by session_id with optional substring query."""
    memory_path = _memory_path()
    if not memory_path.exists():
        return {"ok": True, "items": []}

    needle = query.strip().lower()
    max_items = max(1, min(int(limit), 20))
    items: list[dict[str, Any]] = []
    lines = memory_path.read_text(encoding="utf-8").splitlines()

    for line in reversed(lines):
        if len(items) >= max_items:
            break
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("session_id") != session_id:
            continue
        note = str(item.get("note", ""))
        if needle and needle not in note.lower():
            continue
        items.append(item)

    return {"ok": True, "items": items}


if __name__ == "__main__":
    mcp.run(transport="stdio")
