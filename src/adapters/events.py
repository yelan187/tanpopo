from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IncomingEvent:
    context_id: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IncomingEvent":
        if not isinstance(data, dict):
            raise ValueError("event must be a JSON object")

        context_id = str(data.get("context_id") or "").strip()
        if not context_id:
            raise ValueError("context_id is required")

        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        return cls(context_id=context_id, payload=payload)

    @property
    def event_type(self) -> str:
        return str(self.payload.get("type") or "message").strip() or "message"

    @property
    def text(self) -> str:
        return str(self.payload.get("text") or "").strip()

    @property
    def raw(self) -> dict[str, Any]:
        raw = self.payload.get("raw")
        return raw if isinstance(raw, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "payload": self.payload,
        }
