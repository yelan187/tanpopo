import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from openhands.sdk import Agent, AgentContext, Conversation, LLM
from openhands.sdk.context.condenser import llm_summarizing_condenser
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.context.prompts import render_template
from openhands.sdk.event.base import LLMConvertibleEvent
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.skills import Skill, load_skills_from_dir
from openhands.sdk.utils import maybe_truncate

from ..adapters import InboundMessage, OneBotMessageAdapter
from ..runtime import global_config, register_logger
from ..runtime.gateway import MessageGateway
from ..runtime.mcp import build_mcp_config
from ..runtime.registry import (
    load_runtime_config,
    load_skill_settings,
    reload_request_mtime,
)
from ..event import MessageEvent
from ..ws import WS


logger = register_logger("agent", global_config.log_level)
HOT_GATEWAY_KEYS = {
    "enabled",
    "allowed_sessions",
    "allowed_private_users",
    "allowed_groups",
    "allow_private_without_list",
}
HOT_OPENHANDS_KEYS = {"model", "system_prompt", "workspace", "condenser"}
HOT_CONDENSER_KEYS = {
    "enabled",
    "max_size",
    "max_tokens",
    "keep_first",
    "minimum_progress",
    "hard_context_reset_max_retries",
    "hard_context_reset_context_scaling",
}
HOT_LLM_AUTH_KEYS = {"api_key", "base_url"}
DEFAULT_CONDENSER_CONFIG = {
    "enabled": True,
    "max_size": 80,
    "max_tokens": 120000,
    "keep_first": 2,
    "minimum_progress": 0.1,
}


class StreamingLLMSummarizingCondenser(LLMSummarizingCondenser):
    def _generate_condensation(
        self,
        forgotten_events: Sequence[LLMConvertibleEvent],
        summary_offset: int,
        max_event_str_length: int | None = None,
    ) -> Condensation:
        assert len(forgotten_events) > 0, "No events to condense."

        event_strings = [
            maybe_truncate(str(forgotten_event), truncate_after=max_event_str_length)
            for forgotten_event in forgotten_events
        ]
        prompt = render_template(
            os.path.join(
                os.path.dirname(llm_summarizing_condenser.__file__), "prompts"
            ),
            "summarizing_prompt.j2",
            events=event_strings,
        )
        llm_response = self.llm.completion(
            messages=[Message(role="user", content=[TextContent(text=prompt)])],
            on_token=self._on_condensation_token,
        )

        summary = None
        if llm_response.message.content:
            first_content = llm_response.message.content[0]
            if isinstance(first_content, TextContent):
                summary = first_content.text

        return Condensation(
            forgotten_event_ids=[event.id for event in forgotten_events],
            summary=summary,
            summary_offset=summary_offset,
            llm_response_id=llm_response.id,
        )

    @staticmethod
    def _on_condensation_token(_: object) -> None:
        return


class AgentCore:
    def __init__(self, ws: WS):
        self.ws = ws
        self.workspace_root = Path.cwd().resolve()

        self.locks: dict[str, asyncio.Lock] = {}
        self.conversations: dict[str, Conversation] = {}
        self.message_buffers: dict[str, list[InboundMessage]] = {}
        self.active_sessions: set[str] = set()
        self._init_lock = asyncio.Lock()
        self.runtime_config = load_runtime_config(self.workspace_root)
        self.gateway = MessageGateway(self._effective_agent_config().get("gateway", {}))

        self.llm: LLM | None = None
        self.agent: Agent | None = None
        self._loaded_reload_mtime = 0.0

    def _build_llm(self) -> LLM:
        agent_config = self._effective_agent_config()
        openhands_config = agent_config.get("openhands", {})
        llm_auth = self._effective_llm_auth()

        model = (
            os.getenv("LLM_MODEL")
            or str(openhands_config.get("model", "")).strip()
            # Backward compatibility for older config.yaml files.
            or global_config.llm_models.get("chat_model", "")
        )
        model = self._normalize_litellm_model_name(model)
        api_key = os.getenv("LLM_API_KEY") or llm_auth.get("api_key")
        base_url = os.getenv("LLM_BASE_URL") or llm_auth.get("base_url")
        base_url = self._normalize_openai_base_url(base_url, model)
        return LLM(
            model=model,
            api_key=api_key,
            base_url=base_url,
            stream=True,
            drop_params=True,
            modify_params=False,
            prompt_cache_retention=None,
            reasoning_effort="none",
            reasoning_summary=None,
            extended_thinking_budget=None,
            enable_encrypted_reasoning=False,
        )

    @staticmethod
    def _normalize_litellm_model_name(model: str) -> str:
        clean = str(model).strip()
        if not clean:
            return clean
        if "/" in clean:
            return clean
        return f"openai/{clean}"

    @staticmethod
    def _normalize_openai_base_url(base_url: str, model: str) -> str:
        clean_base = str(base_url).strip()
        if not clean_base:
            return clean_base
        if not str(model).startswith("openai/"):
            return clean_base

        parsed = urlparse(clean_base)
        path = parsed.path.rstrip("/")
        if path.endswith("/v1"):
            return clean_base.rstrip("/")

        if not path:
            new_path = "/v1"
        else:
            new_path = f"{path}/v1"
        return urlunparse(parsed._replace(path=new_path)).rstrip("/")

    def _build_agent(self) -> Agent:
        agent_config = self._effective_agent_config()
        openhands_config = agent_config.get("openhands", {})
        mcp_config = build_mcp_config(
            agent_config,
            self.workspace_root,
            global_config.http_settings,
        )
        system_prompt = (
            str(openhands_config.get("system_prompt", "")).strip()
            or self._default_system_prompt()
        )
        agent_context = AgentContext(skills=self._load_agent_skills())
        condenser = self._build_condenser(openhands_config)

        return Agent(
            llm=self.llm,
            tools=[],
            include_default_tools=[],
            mcp_config=mcp_config,
            agent_context=agent_context,
            system_prompt=system_prompt,
            condenser=condenser,
        )

    def _build_condenser(
        self, openhands_config: dict[str, object]
    ) -> LLMSummarizingCondenser | None:
        if self.llm is None:
            raise RuntimeError("LLM is not initialized")

        raw_config = openhands_config.get("condenser", {})
        condenser_config = dict(DEFAULT_CONDENSER_CONFIG)
        if isinstance(raw_config, dict):
            condenser_config.update(
                {
                    key: value
                    for key, value in raw_config.items()
                    if key in HOT_CONDENSER_KEYS
                }
            )

        if not bool(condenser_config.get("enabled", True)):
            logger.info("OpenHands context condenser 已禁用")
            return None

        max_tokens = _optional_positive_int(condenser_config.get("max_tokens"))
        logger.info(
            "启用 OpenHands context condenser: "
            f"max_size={condenser_config.get('max_size')} max_tokens={max_tokens}"
        )
        return StreamingLLMSummarizingCondenser(
            llm=self.llm,
            max_size=_positive_int(condenser_config.get("max_size"), 80),
            max_tokens=max_tokens,
            keep_first=_non_negative_int(condenser_config.get("keep_first"), 2),
            minimum_progress=_bounded_float(
                condenser_config.get("minimum_progress"), 0.1
            ),
            hard_context_reset_max_retries=_positive_int(
                condenser_config.get("hard_context_reset_max_retries"), 5
            ),
            hard_context_reset_context_scaling=_bounded_float(
                condenser_config.get("hard_context_reset_context_scaling"), 0.8
            ),
        )

    def _effective_agent_config(self) -> dict[str, object]:
        override_agent_config = self.runtime_config.get("agent_config", {})
        if not isinstance(override_agent_config, dict):
            override_agent_config = {}
        hot_override: dict[str, object] = {}

        gateway = override_agent_config.get("gateway")
        if isinstance(gateway, dict):
            hot_override["gateway"] = {
                key: value for key, value in gateway.items() if key in HOT_GATEWAY_KEYS
            }

        openhands = override_agent_config.get("openhands")
        if isinstance(openhands, dict):
            filtered_openhands = {}
            for key, value in openhands.items():
                if key not in HOT_OPENHANDS_KEYS:
                    continue
                if key == "condenser" and isinstance(value, dict):
                    filtered_openhands[key] = {
                        condenser_key: condenser_value
                        for condenser_key, condenser_value in value.items()
                        if condenser_key in HOT_CONDENSER_KEYS
                    }
                else:
                    filtered_openhands[key] = value
            hot_override["openhands"] = filtered_openhands

        return _deep_merge(global_config.agent_config, hot_override)

    def _effective_llm_auth(self) -> dict[str, object]:
        override_llm_auth = self.runtime_config.get("llm_auth", {})
        if not isinstance(override_llm_auth, dict):
            override_llm_auth = {}
        hot_override = {
            key: value for key, value in override_llm_auth.items() if key in HOT_LLM_AUTH_KEYS
        }
        return _deep_merge(global_config.llm_auth, hot_override)

    def _load_agent_skills(self) -> list[Skill]:
        skills_dir = self.workspace_root / ".agents" / "skills"
        if not skills_dir.is_dir():
            return []

        try:
            repo_skills, knowledge_skills, agent_skills = load_skills_from_dir(
                skills_dir
            )
        except Exception as exc:
            logger.warning(f"加载 agent skills 失败: {exc}")
            return []

        skill_settings = load_skill_settings(self.workspace_root)
        discovered = [
            *repo_skills.values(),
            *knowledge_skills.values(),
            *agent_skills.values(),
        ]
        skills = [
            skill
            for skill in discovered
            if bool(skill_settings.get(skill.name, {}).get("enabled", True))
        ]
        logger.info(f"已加载 agent skills: {[skill.name for skill in skills]}")
        return skills

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are Tanpopo, a QQ chat agent. You receive one normalized message batch as JSON. "
            "The JSON has a messages array and may contain one or more buffered messages from "
            "the same QQ session. Treat the messages as a short conversation fragment in arrival "
            "order, focus on the latest user intent, and avoid replying separately to every item "
            "unless that is clearly useful. "
            "Use available MCP tools to act. For QQ replies, call qq_send_text with the target "
            "metadata from the relevant message, usually the latest message. Keep chat replies "
            "short and casual: usually one sentence, at most two short sentences. Do not write "
            "long explanations, numbered lists, or full analysis unless the user explicitly asks "
            "for detail. When a useful answer is too long for one chat message, split it into "
            "several natural qq_send_text calls instead of one wall of text. You do not need to "
            "reply to every message. In groups, stay quiet unless the message is directed at you, "
            "asks for your help, or you have a clearly useful and natural contribution. For short "
            "punctuation, ambient chatter, or messages that do not need your participation, finish "
            "with DONE without calling a QQ send tool. If a tool call succeeds and no further "
            "user-visible action is useful, finish with DONE instead of calling another tool. The "
            "sender's nickname, group card, and display name are available in each message's "
            "metadata. If you are unsure what tools or skills are currently enabled, call "
            "runtime_capabilities before answering. If the user asks you to add, enable, disable, "
            "or inspect skills/MCPs, use plugin-manager and capability MCP tools instead of "
            "guessing. Runtime plugin changes take effect after a reload request and the next "
            "message."
        )

    async def _ensure_agent_ready(self) -> None:
        if self.agent is not None and self.llm is not None:
            return
        async with self._init_lock:
            if self.agent is not None and self.llm is not None:
                return
            self.llm = self._build_llm()
            self.agent = self._build_agent()
            self._loaded_reload_mtime = reload_request_mtime(self.workspace_root)

    async def _reload_agent_if_requested(self) -> None:
        current_mtime = reload_request_mtime(self.workspace_root)
        if current_mtime <= self._loaded_reload_mtime:
            return
        async with self._init_lock:
            current_mtime = reload_request_mtime(self.workspace_root)
            if current_mtime <= self._loaded_reload_mtime:
                return
            logger.info("检测到 reload 请求，重建 agent 和会话")
            self.runtime_config = load_runtime_config(self.workspace_root)
            self.gateway = MessageGateway(
                self._effective_agent_config().get("gateway", {})
            )
            self.agent = None
            self.conversations.clear()
            self.llm = self._build_llm()
            self.agent = self._build_agent()
            self._loaded_reload_mtime = current_mtime

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        lock = self.locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self.locks[session_id] = lock
        return lock

    def _get_or_create_conversation(self, session_id: str) -> Conversation:
        conversation = self.conversations.get(session_id)
        if conversation is not None:
            return conversation

        if self.agent is None:
            raise RuntimeError("Agent is not initialized")

        openhands_config = self._effective_agent_config().get("openhands", {})
        workspace = str(openhands_config.get("workspace", "")).strip() or str(self.workspace_root)
        conversation = Conversation(
            agent=self.agent,
            workspace=workspace,
            token_callbacks=[self._on_token],
        )
        self.conversations[session_id] = conversation
        return conversation

    @staticmethod
    def _on_token(_: object) -> None:
        return

    async def handle_message(self, message_event: MessageEvent) -> None:
        inbound = OneBotMessageAdapter.from_event(message_event)
        await self._reload_agent_if_requested()
        decision = self.gateway.decide(inbound)
        if not decision.accepted:
            logger.info(f"网关拒绝消息[{inbound.session_id}]: {decision.reason}")
            return

        session_id = inbound.session_id
        lock = self._get_session_lock(session_id)
        async with lock:
            if session_id in self.active_sessions:
                self.message_buffers.setdefault(session_id, []).append(inbound)
                logger.info(
                    f"会话处理中，消息进入缓冲[{session_id}] "
                    f"buffer={len(self.message_buffers[session_id])}"
                )
                return
            self.active_sessions.add(session_id)

        messages = [inbound]
        while messages:
            await self._run_openhands_agent_loop(messages)
            async with lock:
                messages = self.message_buffers.pop(session_id, [])
                if messages:
                    logger.info(f"处理缓冲消息[{session_id}] count={len(messages)}")
                else:
                    self.active_sessions.discard(session_id)
                    return

    async def _run_openhands_agent_loop(self, messages: list[InboundMessage]) -> None:
        non_empty_messages = [message for message in messages if message.text]
        if not non_empty_messages:
            logger.debug("空消息批次，跳过")
            return

        session_id = non_empty_messages[0].session_id
        logger.info(
            f"openhands收到消息批次[{session_id}] count={len(non_empty_messages)} "
            f"-> {self._summarize_batch_text(non_empty_messages)}"
        )

        await self._ensure_agent_ready()
        await self._reload_agent_if_requested()
        conversation = self._get_or_create_conversation(session_id)
        prompt = json.dumps(
            self._build_batch_payload(non_empty_messages), ensure_ascii=False
        )

        await asyncio.to_thread(conversation.send_message, prompt)
        try:
            await asyncio.to_thread(conversation.run)
        except Exception as exc:
            logger.error(f"OpenHands回合失败[{session_id}]: {exc}")
            return

        logger.info(f"openhands回合完成[{session_id}]")

    @staticmethod
    def _summarize_batch_text(messages: list[InboundMessage]) -> str:
        text = " | ".join(message.text for message in messages)
        return text[:500]

    @staticmethod
    def _build_batch_payload(messages: list[InboundMessage]) -> dict[str, object]:
        first = messages[0]
        latest = messages[-1]
        lines = []
        for index, message in enumerate(messages, start=1):
            display_name = message.metadata.get("sender_display_name") or str(
                message.metadata.get("user_id", "")
            )
            lines.append(f"{index}. {display_name}: {message.text}")

        return {
            "session_id": first.session_id,
            "channel": first.channel,
            "message_count": len(messages),
            "text": "\n".join(lines),
            "latest_metadata": latest.metadata,
            "messages": [
                {
                    "index": index,
                    **message.to_agent_payload(),
                }
                for index, message in enumerate(messages, start=1)
            ],
            "instruction": (
                "You are receiving one or more buffered messages from the same QQ session. "
                "Read them in order, answer the latest actionable user intent, and use the "
                "metadata from the relevant message as the QQ reply target. Usually send at "
                "most one concise QQ reply for the whole batch, then finish with DONE."
            ),
        }


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _optional_positive_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    parsed = _positive_int(value, 0)
    return parsed or None


def _non_negative_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _bounded_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if 0.0 < parsed < 1.0 else default
