import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from src.event import MessageEvent
from src.runtime import global_config, register_logger

from .events import IncomingEvent


logger = register_logger("onebot-adapter", global_config.log_level)


@dataclass(frozen=True)
class OneBotGatewayDecision:
    accepted: bool
    reason: str = ""


class OneBotMessageAdapter:
    @classmethod
    def from_event(cls, message_event: MessageEvent) -> IncomingEvent:
        return IncomingEvent(
            context_id=cls.get_context_id(message_event),
            payload={
                "type": "message",
                "text": message_event.get_plaintext(with_at=True).strip(),
                "raw": message_event.raw_event,
            },
        )

    @staticmethod
    def get_context_id(message_event: MessageEvent) -> str:
        if message_event.is_group():
            return f"qq:group:{message_event.group_id}"
        return f"qq:private:{message_event.user_id}"


class OneBotGateway:
    def __init__(self, config: dict[str, Any]):
        self.config = config if isinstance(config, dict) else {}

    def decide(self, message_event: MessageEvent) -> OneBotGatewayDecision:
        if not bool(self.config.get("enabled", True)):
            return OneBotGatewayDecision(True, "gateway disabled")

        context_id = OneBotMessageAdapter.get_context_id(message_event)
        allowed_sessions = self._string_set(self.config.get("allowed_sessions"))
        allowed_private_users = self._int_set(self.config.get("allowed_private_users"))
        allowed_groups = self._int_set(self.config.get("allowed_groups"))
        has_allowlist = bool(allowed_sessions or allowed_private_users or allowed_groups)
        if context_id in allowed_sessions:
            return OneBotGatewayDecision(True, "session allowed")

        if message_event.is_private():
            if message_event.user_id in allowed_private_users:
                return OneBotGatewayDecision(True, "private user allowed")
            if has_allowlist:
                return OneBotGatewayDecision(False, "private user denied")
            return OneBotGatewayDecision(
                bool(self.config.get("allow_private_without_list", False)),
                "private fallback",
            )

        if message_event.is_group():
            if message_event.group_id in allowed_groups:
                return OneBotGatewayDecision(True, "group allowed")
            if has_allowlist:
                return OneBotGatewayDecision(False, "group denied")
            return OneBotGatewayDecision(False, "group list is empty")

        return OneBotGatewayDecision(
            False, f"unsupported message_type: {message_event.message_type}"
        )

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


class OneBotWebhookAdapter:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.gateway = OneBotGateway(_onebot_gateway_config())

    async def handle_message(self, message_event: MessageEvent) -> None:
        decision = self.gateway.decide(message_event)
        if not decision.accepted:
            logger.info(
                "OneBot 网关拒绝消息"
                f"[{OneBotMessageAdapter.get_context_id(message_event)}]: "
                f"{decision.reason}"
            )
            return

        event = OneBotMessageAdapter.from_event(message_event)
        await asyncio.to_thread(self._post_event, event)

    def _post_event(self, event: IncomingEvent) -> None:
        payload = json.dumps(event.to_dict(), ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as resp:
                resp.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            logger.warning(
                f"转发 OneBot 事件到 Core 失败: status={exc.code} detail={detail}"
            )
        except Exception as exc:
            logger.warning(f"转发 OneBot 事件到 Core 失败: {exc}")


def _onebot_gateway_config() -> dict[str, Any]:
    adapter_config = global_config.adapter_config.get("onebot", {})
    if isinstance(adapter_config, dict):
        gateway_config = adapter_config.get("gateway")
        if isinstance(gateway_config, dict) and gateway_config:
            return gateway_config

    legacy_config = global_config.agent_config.get("gateway", {})
    return legacy_config if isinstance(legacy_config, dict) else {}
