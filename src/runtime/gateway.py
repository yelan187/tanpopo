from dataclasses import dataclass
from typing import Any

from src.adapters.onebot import InboundMessage


@dataclass(frozen=True)
class GatewayDecision:
    accepted: bool
    reason: str = ""


class MessageGateway:
    def __init__(self, config: dict[str, Any]):
        self.config = config if isinstance(config, dict) else {}

    def decide(self, inbound: InboundMessage) -> GatewayDecision:
        if not bool(self.config.get("enabled", True)):
            return GatewayDecision(True, "gateway disabled")

        allowed_sessions = self._string_set(self.config.get("allowed_sessions"))
        allowed_private_users = self._int_set(self.config.get("allowed_private_users"))
        allowed_groups = self._int_set(self.config.get("allowed_groups"))
        has_allowlist = bool(allowed_sessions or allowed_private_users or allowed_groups)
        if inbound.session_id in allowed_sessions:
            return GatewayDecision(True, "session allowed")

        message_type = inbound.metadata.get("message_type")
        if message_type == "private":
            user_id = self._to_int(inbound.metadata.get("user_id"))
            if user_id in allowed_private_users:
                return GatewayDecision(True, "private user allowed")
            if has_allowlist:
                return GatewayDecision(False, "private user denied")
            return GatewayDecision(
                bool(self.config.get("allow_private_without_list", False)),
                "private fallback",
            )

        if message_type == "group":
            group_id = self._to_int(inbound.metadata.get("group_id"))
            if group_id in allowed_groups:
                return GatewayDecision(True, "group allowed")
            if has_allowlist:
                return GatewayDecision(False, "group denied")
            return GatewayDecision(False, "group list is empty")

        return GatewayDecision(False, f"unsupported message_type: {message_type}")

    @staticmethod
    def _string_set(value: Any) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}

    @staticmethod
    def _int_set(value: Any) -> set[int]:
        if not isinstance(value, list):
            return set()
        result: set[int] = set()
        for item in value:
            try:
                result.add(int(item))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
