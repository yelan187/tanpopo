from dataclasses import dataclass, field
from typing import Any

from src.event import MessageEvent


@dataclass(frozen=True)
class InboundMessage:
    session_id: str
    channel: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    response_instruction: str = ""

    def to_agent_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "channel": self.channel,
            "text": self.text,
            "metadata": self.metadata,
            "instruction": self.response_instruction,
        }


class OneBotMessageAdapter:
    channel = "onebot"

    @classmethod
    def from_event(cls, message_event: MessageEvent) -> InboundMessage:
        sender_nickname = getattr(message_event.sender, "nickname", "")
        sender_card = getattr(message_event.sender, "card", "")
        return InboundMessage(
            session_id=cls.get_session_id(message_event),
            channel=cls.channel,
            text=message_event.get_plaintext(with_at=True).strip(),
            metadata={
                "message_type": message_event.message_type,
                "group_id": message_event.group_id,
                "user_id": message_event.user_id,
                "sender_nickname": sender_nickname,
                "sender_card": sender_card,
                "sender_display_name": sender_card or sender_nickname or str(message_event.user_id),
                "message_id": message_event.message_id,
                "raw_message": message_event.raw_message,
                "at_list": message_event.at_list,
                "is_tome": message_event.is_tome,
            },
            response_instruction=(
                "Reply via QQ MCP tools when a response is useful. "
                "Use metadata fields as the message target. "
                "The agent input may contain a messages array with one or more buffered messages. "
                "Answer the latest actionable user intent instead of replying to every message. "
                "For normal group chat, do not quote unless quoting is necessary. "
                "For simple replies, send one QQ message and then finish with DONE."
            ),
        )

    @staticmethod
    def get_session_id(message_event: MessageEvent) -> str:
        if message_event.is_group():
            return f"group:{message_event.group_id}"
        return f"private:{message_event.user_id}"
