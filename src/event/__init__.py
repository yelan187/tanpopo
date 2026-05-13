import time
from typing import Any

from .qq_face_map import get_qq_face_name


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class MessageEvent:
    def __init__(self, message_event: dict[str, Any]):
        data = message_event if isinstance(message_event, dict) else {}

        self.raw_event = data
        self.post_type = data.get("post_type")
        self.message_type = data.get("message_type")
        self.sub_type = data.get("sub_type")

        self.self_id = _to_int(data.get("self_id"))
        self.user_id = _to_int(data.get("user_id"))
        self.group_id = _to_int(data.get("group_id"))
        self.message_id = _to_int(data.get("message_id"))
        self.font = _to_int(data.get("font"))

        self.time_epoch = _to_int(data.get("time"))
        if self.time_epoch is not None:
            self.time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.time_epoch))
        else:
            self.time = ""

        self.raw_message = str(data.get("raw_message") or "")
        self.anonymous = Anonymous(data.get("anonymous"))
        self.sender = Sender(data.get("sender"))
        self.message = Message.from_onebot(data.get("message"))

        self.at_list = self.get_at_list()
        self.is_tome = str(self.self_id) in self.at_list or self.at_list == ["all"]

    def is_group(self) -> bool:
        return self.message_type == "group"

    def is_private(self) -> bool:
        return self.message_type == "private"

    def update_discriptions(self, discriptions: list[str]) -> None:
        if not discriptions:
            return
        self.message.update_discriptions(discriptions)

    def update_reply(self, reply: "MessageEvent" | None) -> None:
        if reply is None:
            return
        self.message.update_reply(reply)

    def get_plaintext(self, with_at: bool = True, loop: bool = False) -> str:
        parts: list[str] = []
        for segment in self.message.segments:
            parts.append(self._segment_to_plaintext(segment, with_at=with_at, loop=loop))
        return " ".join([part for part in parts if part]).strip()

    def _segment_to_plaintext(self, segment: "Segment", with_at: bool, loop: bool) -> str:
        seg_type = segment.type
        data = segment.data

        if seg_type == "text":
            return str(data.get("text") or "")

        if seg_type == "at":
            if not with_at:
                return ""
            qq = data.get("qq")
            if qq == "all":
                return "@all"
            return f"@{qq}" if qq is not None else "@"

        if seg_type == "reply" and not loop:
            reply_id = data.get("id")
            reply_plaintext = data.get("plaintext")
            if reply_plaintext:
                return f"[引用:{reply_plaintext}]"
            return f"[引用:{reply_id}]" if reply_id is not None else "[引用]"

        if seg_type == "image":
            desc = data.get("discription")
            if desc:
                return f"[图片:{desc}]"
            return "[图片]"

        if seg_type == "face":
            face_id = data.get("id")
            if face_id is None:
                return "[表情]"
            face_name = get_qq_face_name(face_id)
            return f"[表情:{face_name}]"

        if seg_type in ("mface", "market_face"):
            summary = (
                data.get("summary")
                or data.get("emoji_package_name")
                or data.get("key")
            )
            if summary is None:
                face_id = data.get("emoji_id") or data.get("face_id") or data.get("id")
                if face_id is not None:
                    summary = get_qq_face_name(face_id)
            return f"[表情:{summary}]" if summary else "[表情]"

        if seg_type == "record":
            return "[语音]"
        if seg_type == "video":
            return "[视频]"
        if seg_type == "file":
            return "[文件]"
        if seg_type == "json":
            return "[JSON消息]"
        if seg_type == "xml":
            return "[XML消息]"
        if seg_type == "share":
            title = data.get("title")
            return f"[分享:{title}]" if title else "[分享]"
        if seg_type == "contact":
            contact_type = data.get("type")
            contact_id = data.get("id")
            if contact_type and contact_id:
                return f"[名片:{contact_type}:{contact_id}]"
            return "[名片]"
        if seg_type == "location":
            title = data.get("title")
            return f"[位置:{title}]" if title else "[位置]"
        if seg_type == "poke":
            return "[戳一戳]"
        if seg_type == "dice":
            return "[骰子]"
        if seg_type == "rps":
            return "[猜拳]"
        if seg_type == "forward":
            return "[合并转发]"
        if seg_type == "node":
            return "[转发节点]"

        return f"[{seg_type}]" if seg_type else ""

    def get_text(self) -> str:
        text_parts: list[str] = []
        for segment in self.message.segments:
            if segment.type == "text":
                text_parts.append(str(segment.data.get("text") or ""))
        return "".join(text_parts)

    def get_at_list(self) -> list[str]:
        result: list[str] = []
        for segment in self.message.segments:
            if segment.type != "at":
                continue
            qq = segment.data.get("qq")
            if qq == "all":
                return ["all"]
            if qq is not None:
                result.append(str(qq))
        return result

    def get_imgs_url(self) -> tuple[list[str], list[bool]]:
        urls: list[str] = []
        is_meme: list[bool] = []
        for segment in self.message.segments:
            if segment.type != "image":
                continue

            url = segment.data.get("url")
            if url is not None:
                urls.append(str(url))
            else:
                file_value = segment.data.get("file")
                urls.append(str(file_value or ""))

            try:
                is_meme.append(int(segment.data.get("sub_type")) == 1)
            except (TypeError, ValueError):
                is_meme.append(False)

        return urls, is_meme

    def get_id(self) -> int | None:
        return self.user_id if self.is_private() else self.group_id


class Segment:
    def __init__(self, type: str | None = None, data: dict[str, Any] | None = None):
        self.type = str(type or "")
        self.data = data if isinstance(data, dict) else {}

    @classmethod
    def from_onebot(cls, payload: Any) -> "Segment":
        if isinstance(payload, dict):
            seg_type = payload.get("type")
            seg_data = payload.get("data")
            return cls(type=seg_type, data=seg_data if isinstance(seg_data, dict) else {})
        if isinstance(payload, str):
            return cls(type="text", data={"text": payload})
        return cls(type="", data={})


class Anonymous:
    def __init__(self, data: dict[str, Any] | None = None):
        source = data if isinstance(data, dict) else {}
        self.id = _to_int(source.get("id"))
        self.name = source.get("name")
        self.flag = source.get("flag")


class Sender:
    def __init__(self, data: dict[str, Any] | None = None):
        source = data if isinstance(data, dict) else {}
        self.user_id = _to_int(source.get("user_id"))
        self.nickname = source.get("nickname")
        self.card = source.get("card")
        self.sex = source.get("sex")
        self.age = _to_int(source.get("age"))
        self.area = source.get("area")
        self.level = source.get("level")
        self.role = source.get("role")
        self.title = source.get("title")


class Message:
    def __init__(self, segments: list[Segment] | None = None):
        self.segments = segments if isinstance(segments, list) else []

    @classmethod
    def from_onebot(cls, payload: Any) -> "Message":
        if isinstance(payload, list):
            return cls([Segment.from_onebot(item) for item in payload])
        if isinstance(payload, str):
            return cls([Segment(type="text", data={"text": payload})])
        if isinstance(payload, dict):
            return cls([Segment.from_onebot(payload)])
        return cls([])

    def update_discriptions(self, discriptions: list[str]) -> None:
        cnt = 0
        for segment in self.segments:
            if segment.type != "image":
                continue
            if cnt >= len(discriptions):
                break
            segment.data["discription"] = discriptions[cnt]
            cnt += 1

    def update_reply(self, reply: MessageEvent) -> None:
        for segment in self.segments:
            if segment.type == "reply":
                segment.data["plaintext"] = reply.get_plaintext(loop=True)
