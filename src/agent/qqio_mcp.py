import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from fastmcp import FastMCP

from src.bot.config import global_config
from src.bot.logger import register_logger
from src.event import MessageEvent


logger = register_logger("qqio-mcp", global_config.log_level)
mcp = FastMCP("tanpopo-qqio")


def _onebot_api_url(action: str) -> str:
    host = os.getenv("TANPOPO_HTTP_HOST") or str(global_config.http_settings.get("host", "127.0.0.1"))
    port = os.getenv("TANPOPO_HTTP_PORT") or str(global_config.http_settings.get("port", 3000))
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
        return {
            "ok": False,
            "error": str(exc),
            "action": action,
        }

    if not raw:
        return {
            "ok": True,
            "action": action,
            "data": None,
        }

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": True,
            "action": action,
            "raw": raw,
        }

    if isinstance(parsed, dict):
        status = parsed.get("status")
        retcode = parsed.get("retcode")
        parsed["ok"] = status == "ok" and retcode in (0, None)
        parsed.setdefault("action", action)
        return parsed

    return {
        "ok": True,
        "action": action,
        "data": parsed,
    }


def _json_or_empty(value: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    obj = json.loads(value)
    if not isinstance(obj, dict):
        raise ValueError("params_json must be a JSON object")
    return obj


def _memory_path() -> Path:
    memory_file = os.getenv("TANPOPO_MEMORY_FILE")
    if memory_file:
        return Path(memory_file)
    return Path.cwd() / "tmp" / "agent_memories.jsonl"


def _message_target(message_type: str, group_id: int | None, user_id: int | None) -> dict[str, int]:
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
def qq_call_api(action: str, params_json: str = "{}") -> dict[str, Any]:
    """Call OneBot API with raw action and params JSON object."""
    return _post_onebot(action, _json_or_empty(params_json))


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
    """Send text message to group/private chat."""
    clean_text = text.strip()
    if not clean_text:
        return {"ok": False, "error": "text is empty"}

    message: list[dict[str, Any]] = []
    if reply_to_message_id is not None:
        message.append({"type": "reply", "data": {"id": int(reply_to_message_id)}})
    if at_user_id is not None and message_type == "group":
        message.append({"type": "at", "data": {"qq": int(at_user_id)}})
        clean_text = " " + clean_text
    message.append({"type": "text", "data": {"text": clean_text}})

    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    params: dict[str, Any] = {
        "message_type": message_type,
        "message": message,
        "auto_escape": bool(auto_escape),
    }
    params.update(target)
    result = _post_onebot("send_msg", params)
    logger.info(f"qqio_mcp发送文本 -> {clean_text}")
    return result


@mcp.tool
def qq_send_image(
    message_type: str,
    file: str,
    group_id: int | None = None,
    user_id: int | None = None,
    reply_to_message_id: int | None = None,
    image_type: str = "",
    cache: bool = True,
    proxy: bool = True,
    timeout: int = 0,
) -> dict[str, Any]:
    """Send image segment. `file` supports path/url/base64://..."""
    clean_file = file.strip()
    if not clean_file:
        return {"ok": False, "error": "file is empty"}

    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    image_data: dict[str, Any] = {
        "file": clean_file,
        "cache": "1" if cache else "0",
        "proxy": "1" if proxy else "0",
    }
    if timeout > 0:
        image_data["timeout"] = str(timeout)
    if image_type.strip():
        image_data["type"] = image_type.strip()

    message: list[dict[str, Any]] = []
    if reply_to_message_id is not None:
        message.append({"type": "reply", "data": {"id": int(reply_to_message_id)}})
    message.append({"type": "image", "data": image_data})

    params: dict[str, Any] = {
        "message_type": message_type,
        "message": message,
    }
    params.update(target)
    return _post_onebot("send_msg", params)


@mcp.tool
def qq_send_record(
    message_type: str,
    file: str,
    group_id: int | None = None,
    user_id: int | None = None,
    magic: bool = False,
) -> dict[str, Any]:
    """Send voice segment to group/private chat."""
    clean_file = file.strip()
    if not clean_file:
        return {"ok": False, "error": "file is empty"}

    try:
        target = _message_target(message_type, group_id, user_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    params: dict[str, Any] = {
        "message_type": message_type,
        "message": [
            {
                "type": "record",
                "data": {
                    "file": clean_file,
                    "magic": "1" if magic else "0",
                },
            }
        ],
    }
    params.update(target)
    return _post_onebot("send_msg", params)


@mcp.tool
def qq_delete_msg(message_id: int) -> dict[str, Any]:
    """Recall one message by message_id."""
    return _post_onebot("delete_msg", {"message_id": int(message_id)})


@mcp.tool
def qq_get_msg(message_id: int) -> dict[str, Any]:
    """Get message detail by message_id."""
    return _post_onebot("get_msg", {"message_id": int(message_id)})


@mcp.tool
def qq_get_login_info() -> dict[str, Any]:
    """Get bot account information."""
    return _post_onebot("get_login_info", {})


@mcp.tool
def qq_get_stranger_info(user_id: int, no_cache: bool = False) -> dict[str, Any]:
    """Get stranger profile."""
    return _post_onebot("get_stranger_info", {"user_id": int(user_id), "no_cache": no_cache})


@mcp.tool
def qq_get_friend_list() -> dict[str, Any]:
    """Get friend list."""
    return _post_onebot("get_friend_list", {})


@mcp.tool
def qq_get_group_list() -> dict[str, Any]:
    """Get group list."""
    return _post_onebot("get_group_list", {})


@mcp.tool
def qq_get_group_info(group_id: int, no_cache: bool = False) -> dict[str, Any]:
    """Get group information by group_id."""
    return _post_onebot("get_group_info", {"group_id": int(group_id), "no_cache": no_cache})


@mcp.tool
def qq_get_group_member_info(group_id: int, user_id: int, no_cache: bool = False) -> dict[str, Any]:
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
def qq_set_group_ban(group_id: int, user_id: int, duration: int = 1800) -> dict[str, Any]:
    """Ban/unban group member. duration=0 means unban."""
    safe_duration = max(0, int(duration))
    return _post_onebot(
        "set_group_ban",
        {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "duration": safe_duration,
        },
    )


@mcp.tool
def qq_set_group_kick(group_id: int, user_id: int, reject_add_request: bool = False) -> dict[str, Any]:
    """Kick member from group."""
    return _post_onebot(
        "set_group_kick",
        {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "reject_add_request": reject_add_request,
        },
    )


@mcp.tool
def qq_set_group_whole_ban(group_id: int, enable: bool = True) -> dict[str, Any]:
    """Enable/disable whole group mute."""
    return _post_onebot("set_group_whole_ban", {"group_id": int(group_id), "enable": enable})


@mcp.tool
def qq_set_group_card(group_id: int, user_id: int, card: str = "") -> dict[str, Any]:
    """Set group card (remark) for a member."""
    return _post_onebot(
        "set_group_card",
        {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "card": card,
        },
    )


@mcp.tool
def qq_set_group_name(group_id: int, group_name: str) -> dict[str, Any]:
    """Set group name."""
    clean_name = group_name.strip()
    if not clean_name:
        return {"ok": False, "error": "group_name is empty"}
    return _post_onebot(
        "set_group_name",
        {
            "group_id": int(group_id),
            "group_name": clean_name,
        },
    )


@mcp.tool
def qq_parse_message_event(event_json: str) -> dict[str, Any]:
    """Parse OneBot message event JSON with detailed segment decoding."""
    try:
        payload = json.loads(event_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid json: {exc}"}

    if not isinstance(payload, dict):
        return {"ok": False, "error": "event_json must decode to JSON object"}

    message_event = MessageEvent(payload)
    segments: list[dict[str, Any]] = []
    for segment in message_event.message.segments:
        detail = {
            "type": segment.type,
            "data": segment.data,
            "as_text": message_event._segment_to_plaintext(segment, with_at=True, loop=False),
        }
        if segment.type == "at":
            qq = segment.data.get("qq")
            detail["target"] = "all" if qq == "all" else str(qq) if qq is not None else None
        elif segment.type == "reply":
            detail["reply_message_id"] = segment.data.get("id")
        elif segment.type == "face":
            face_id = segment.data.get("id")
            detail["face_id"] = face_id
            detail["face_name"] = get_face_name(face_id)
        elif segment.type == "image":
            detail["file"] = segment.data.get("file")
            detail["url"] = segment.data.get("url")
        segments.append(detail)

    return {
        "ok": True,
        "parsed": {
            "post_type": message_event.post_type,
            "message_type": message_event.message_type,
            "sub_type": message_event.sub_type,
            "time": message_event.time,
            "time_epoch": message_event.time_epoch,
            "self_id": message_event.self_id,
            "message_id": message_event.message_id,
            "group_id": message_event.group_id,
            "user_id": message_event.user_id,
            "raw_message": message_event.raw_message,
            "plaintext": message_event.get_plaintext(with_at=True),
            "plaintext_without_at": message_event.get_plaintext(with_at=False),
            "at_list": message_event.at_list,
            "is_tome": message_event.is_tome,
            "anonymous": {
                "id": message_event.anonymous.id,
                "name": message_event.anonymous.name,
                "flag": message_event.anonymous.flag,
            },
            "sender": {
                "user_id": message_event.sender.user_id,
                "nickname": message_event.sender.nickname,
                "card": message_event.sender.card,
                "sex": message_event.sender.sex,
                "age": message_event.sender.age,
                "area": message_event.sender.area,
                "level": message_event.sender.level,
                "role": message_event.sender.role,
                "title": message_event.sender.title,
            },
            "segments": segments,
        },
    }


def get_face_name(face_id: Any) -> str | None:
    if face_id is None:
        return None
    try:
        from src.event.qq_face_map import get_qq_face_name

        return get_qq_face_name(face_id)
    except Exception:
        return str(face_id)


@mcp.tool
def memory_append(session_id: str, note: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Append one memory note to local jsonl storage."""
    clean_note = note.strip()
    if not clean_note:
        return {"ok": False, "error": "note is empty"}

    memory_path = _memory_path()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "session_id": session_id,
        "note": clean_note,
        "tags": tags if isinstance(tags, list) else [],
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
