import asyncio
import json
import logging
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
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

from ..adapters import IncomingEvent
from ..runtime import global_config, register_logger
from ..runtime.mcp import build_mcp_config
from ..runtime.registry import (
    load_runtime_config,
    load_skill_settings,
    reload_request_mtime,
)


logger = register_logger("agent", global_config.log_level)
TRACE_LOGGERS = ("openhands", "fastmcp", "mcp", "litellm", "LiteLLM")
HOT_OPENHANDS_KEYS = {
    "model",
    "system_prompt",
    "workspace",
    "condenser",
    "debug_trace",
    "prewarm",
}
HOT_CONTEXT_KEYS = {
    "idle_ttl_seconds",
    "max_active_contexts",
    "turn_timeout_seconds",
}
HOT_CONDENSER_KEYS = {
    "enabled",
    "max_size",
    "max_tokens",
    "keep_first",
    "minimum_progress",
    "hard_context_reset_max_retries",
    "hard_context_reset_context_scaling",
}
HOT_PREWARM_KEYS = {"enabled", "timeout_seconds"}
HOT_LLM_AUTH_KEYS = {"api_key", "base_url"}
DEFAULT_CONDENSER_CONFIG = {
    "enabled": True,
    "max_size": 80,
    "max_tokens": 120000,
    "keep_first": 2,
    "minimum_progress": 0.1,
}
DEFAULT_CONTEXT_CONFIG = {
    "idle_ttl_seconds": 21600,
    "max_active_contexts": 128,
    "turn_timeout_seconds": 120,
}
DEFAULT_PREWARM_CONFIG = {
    "enabled": True,
    "timeout_seconds": 90,
}
PREWARM_CONTEXT_ID = "__tanpopo__:prewarm"


@dataclass
class ContextState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    buffer: list[IncomingEvent] = field(default_factory=list)
    busy: bool = False
    close_requested: bool = False
    runner: asyncio.Task | None = None
    last_active_at: float = field(default_factory=time.time)
    message_count: int = 0


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
    def __init__(self):
        self.workspace_root = Path.cwd().resolve()

        self.contexts: dict[str, ContextState] = {}
        self._contexts_lock = asyncio.Lock()
        self.conversations: dict[str, Conversation] = {}
        self._init_lock = asyncio.Lock()
        self.runtime_config = load_runtime_config(self.workspace_root)

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
            global_config.core_settings,
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

        context = override_agent_config.get("context")
        if isinstance(context, dict):
            hot_override["context"] = {
                key: value for key, value in context.items() if key in HOT_CONTEXT_KEYS
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
                elif key == "prewarm" and isinstance(value, dict):
                    filtered_openhands[key] = {
                        prewarm_key: prewarm_value
                        for prewarm_key, prewarm_value in value.items()
                        if prewarm_key in HOT_PREWARM_KEYS
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
            "You are Tanpopo, an event-driven chat agent. You receive one normalized event batch "
            "as JSON. The JSON has context_id and events fields, and each event has payload. "
            "For OneBot QQ messages, payload.raw is the original OneBot event and already contains "
            "message_type, group_id, user_id, message_id, sender, and message segments. Treat "
            "buffered events as a short fragment in arrival order, focus on the latest actionable "
            "intent, and avoid replying separately to every item unless useful. Use available MCP "
            "tools to act. For QQ replies, call qq_send_text with fields from the relevant "
            "payload.raw, usually the latest event. Keep chat replies short and casual: usually "
            "one sentence, at most two short sentences. Do not write long explanations, numbered "
            "lists, or full analysis unless the user explicitly asks for detail. When a useful "
            "answer is too long for one chat message, split it into several natural qq_send_text "
            "calls instead of one wall of text. You do not need to reply to every event. In groups, "
            "stay quiet unless the message is directed at you, asks for your help, or you have a "
            "clearly useful and natural contribution. For short punctuation, ambient chatter, or "
            "events that do not need your participation, finish with DONE without calling a QQ send "
            "tool. If a tool call succeeds and no further user-visible action is useful, finish "
            "with DONE instead of calling another tool. If you want to forget a stale short-term "
            "conversation, use the context MCP tools to close or reset that context. If you are "
            "unsure what tools or skills are currently enabled, call runtime_capabilities before "
            "answering. If the user asks you to inspect a webpage or URL, use fetch tools when "
            "available and summarize briefly. If the user asks you to add, enable, disable, or "
            "inspect skills/MCPs, use plugin-manager and capability MCP tools instead of guessing. "
            "Write self-authored reusable MCP plugins under .agents/mcps/{name}/server.py, register "
            "them with plugin-manager, and keep scratch files in agent_workspace or tmp. Runtime "
            "plugin changes take effect after a reload request and the next message."
        )

    async def _ensure_agent_ready(self) -> None:
        if self.agent is not None and self.llm is not None:
            return
        async with self._init_lock:
            if self.agent is not None and self.llm is not None:
                return
            self._configure_trace_logging()
            self.llm = self._build_llm()
            self.agent = self._build_agent()
            self._loaded_reload_mtime = reload_request_mtime(self.workspace_root)

    async def prewarm(self) -> bool:
        prewarm_config = self._prewarm_config()
        if not _bool_value(prewarm_config.get("enabled"), True):
            logger.info("OpenHands 启动预热已禁用")
            return False

        timeout_seconds = _positive_int(
            prewarm_config.get("timeout_seconds"),
            int(DEFAULT_PREWARM_CONFIG["timeout_seconds"]),
        )
        logger.info(f"开始 OpenHands 启动预热 timeout={timeout_seconds}s")
        event = IncomingEvent(
            context_id=PREWARM_CONTEXT_ID,
            payload={
                "type": "prewarm",
                "text": (
                    "Startup prewarm only. Do not call tools. "
                    "Reply exactly DONE."
                ),
                "raw": {},
            },
        )

        try:
            ok = await self._run_openhands_agent_loop(
                PREWARM_CONTEXT_ID,
                [event],
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            logger.warning(f"OpenHands 启动预热失败: {exc}")
            ok = False
        finally:
            self.conversations.pop(PREWARM_CONTEXT_ID, None)

        if ok:
            logger.info("OpenHands 启动预热完成")
        else:
            logger.warning("OpenHands 启动预热未完成，继续启动服务")
        return ok

    async def _reload_agent_if_requested(self) -> None:
        current_mtime = reload_request_mtime(self.workspace_root)
        if current_mtime <= self._loaded_reload_mtime:
            return
        async with self._init_lock:
            current_mtime = reload_request_mtime(self.workspace_root)
            if current_mtime <= self._loaded_reload_mtime:
                return
            logger.info("检测到 reload 请求，重建 agent 和会话")
            previous_runtime_config = self.runtime_config
            previous_llm = self.llm
            previous_agent = self.agent
            try:
                self.runtime_config = load_runtime_config(self.workspace_root)
                self._configure_trace_logging()
                new_llm = self._build_llm()
                self.llm = new_llm
                new_agent = self._build_agent()
            except Exception as exc:
                self.runtime_config = previous_runtime_config
                self.llm = previous_llm
                self.agent = previous_agent
                self._loaded_reload_mtime = current_mtime
                logger.error(f"重建 agent 失败，保留旧实例: {exc}")
                return

            self.llm = new_llm
            self.agent = new_agent
            self.conversations.clear()
            self._loaded_reload_mtime = current_mtime

    def _context_config(self) -> dict[str, object]:
        raw_config = self._effective_agent_config().get("context", {})
        context_config = dict(DEFAULT_CONTEXT_CONFIG)
        if isinstance(raw_config, dict):
            context_config.update(
                {
                    key: value
                    for key, value in raw_config.items()
                    if key in HOT_CONTEXT_KEYS
                }
            )
        return context_config

    def _prewarm_config(self) -> dict[str, object]:
        openhands_config = self._effective_agent_config().get("openhands", {})
        raw_config = {}
        if isinstance(openhands_config, dict):
            candidate = openhands_config.get("prewarm", {})
            if isinstance(candidate, dict):
                raw_config = candidate

        prewarm_config = dict(DEFAULT_PREWARM_CONFIG)
        prewarm_config.update(
            {
                key: value
                for key, value in raw_config.items()
                if key in HOT_PREWARM_KEYS
            }
        )
        return prewarm_config

    def _turn_timeout_seconds(self) -> int:
        context_config = self._context_config()
        return _non_negative_int(
            context_config.get("turn_timeout_seconds"),
            int(DEFAULT_CONTEXT_CONFIG["turn_timeout_seconds"]),
        )

    def _debug_trace_enabled(self) -> bool:
        openhands_config = self._effective_agent_config().get("openhands", {})
        if not isinstance(openhands_config, dict):
            return False
        return _bool_value(openhands_config.get("debug_trace"), False)

    def _configure_trace_logging(self) -> None:
        level = logging.INFO if self._debug_trace_enabled() else logging.ERROR
        for logger_name in TRACE_LOGGERS:
            logging.getLogger(logger_name).setLevel(level)

    async def _get_context_state(self, context_id: str) -> ContextState:
        async with self._contexts_lock:
            self._cleanup_contexts_locked()
            state = self.contexts.get(context_id)
            if state is None:
                state = ContextState()
                self.contexts[context_id] = state
            return state

    def _cleanup_contexts_locked(self) -> None:
        context_config = self._context_config()
        idle_ttl = _positive_int(
            context_config.get("idle_ttl_seconds"),
            int(DEFAULT_CONTEXT_CONFIG["idle_ttl_seconds"]),
        )
        max_active = _positive_int(
            context_config.get("max_active_contexts"),
            int(DEFAULT_CONTEXT_CONFIG["max_active_contexts"]),
        )
        now = time.time()

        for context_id, state in list(self.contexts.items()):
            if state.busy:
                continue
            if now - state.last_active_at > idle_ttl:
                self.contexts.pop(context_id, None)
                self.conversations.pop(context_id, None)
                logger.info(f"回收空闲上下文[{context_id}]")

        if len(self.contexts) <= max_active:
            return

        idle_contexts = [
            (context_id, state)
            for context_id, state in self.contexts.items()
            if not state.busy
        ]
        idle_contexts.sort(key=lambda item: item[1].last_active_at)
        for context_id, _ in idle_contexts[
            : max(0, len(self.contexts) - max_active)
        ]:
            self.contexts.pop(context_id, None)
            self.conversations.pop(context_id, None)
            logger.info(f"按 LRU 回收上下文[{context_id}]")

    def _get_or_create_conversation(self, context_id: str) -> Conversation:
        conversation = self.conversations.get(context_id)
        if conversation is not None:
            return conversation

        if self.agent is None:
            raise RuntimeError("Agent is not initialized")

        self._configure_trace_logging()
        openhands_config = self._effective_agent_config().get("openhands", {})
        workspace = str(openhands_config.get("workspace", "")).strip() or str(
            self.workspace_root
        )
        conversation_kwargs: dict[str, Any] = {
            "agent": self.agent,
            "workspace": workspace,
            "token_callbacks": [self._on_token],
        }
        if not self._debug_trace_enabled():
            conversation_kwargs["visualizer"] = None
        conversation = Conversation(**conversation_kwargs)
        self.conversations[context_id] = conversation
        return conversation

    @staticmethod
    def _on_token(_: object) -> None:
        return

    async def handle_incoming_event(self, event: IncomingEvent) -> None:
        await self._reload_agent_if_requested()

        context_id = event.context_id
        state = await self._get_context_state(context_id)
        async with state.lock:
            state.last_active_at = time.time()
            state.message_count += 1
            if state.busy:
                state.buffer.append(event)
                logger.info(
                    f"上下文处理中，事件进入缓冲[{context_id}] "
                    f"buffer={len(state.buffer)}"
                )
                return
            initial_events = [*state.buffer, event]
            state.buffer = []
            state.busy = True
            state.close_requested = False

        runner = asyncio.create_task(
            self._run_context_loop(context_id, initial_events)
        )
        state.runner = runner
        runner.add_done_callback(self._log_context_runner_result)

    async def _run_context_loop(
        self, context_id: str, events: list[IncomingEvent]
    ) -> None:
        try:
            current_events = events
            while current_events:
                await self._run_openhands_agent_loop(context_id, current_events)

                state = self.contexts.get(context_id)
                if state is None:
                    return

                remove_context = False
                async with state.lock:
                    state.last_active_at = time.time()
                    if state.close_requested:
                        state.buffer.clear()
                        state.busy = False
                        state.runner = None
                        remove_context = True
                        current_events = []
                    else:
                        current_events = state.buffer
                        state.buffer = []
                        if current_events:
                            logger.info(
                                f"处理缓冲事件[{context_id}] count={len(current_events)}"
                            )
                        else:
                            state.busy = False
                            state.runner = None
                            return

                if remove_context:
                    await self._remove_context(context_id)
                    return
        finally:
            state = self.contexts.get(context_id)
            if state is not None:
                async with state.lock:
                    state.busy = False
                    state.runner = None

    async def _run_openhands_agent_loop(
        self,
        context_id: str,
        events: list[IncomingEvent],
        timeout_seconds: int | None = None,
    ) -> bool:
        logger.info(
            f"openhands收到事件批次[{context_id}] count={len(events)} "
            f"-> {self._summarize_batch_text(events)}"
        )

        await self._ensure_agent_ready()
        await self._reload_agent_if_requested()
        conversation = self._get_or_create_conversation(context_id)
        prompt = json.dumps(
            self._build_batch_payload(context_id, events), ensure_ascii=False
        )

        timeout = (
            self._turn_timeout_seconds()
            if timeout_seconds is None
            else _non_negative_int(timeout_seconds, self._turn_timeout_seconds())
        )
        try:
            turn = asyncio.to_thread(self._run_conversation_sync, conversation, prompt)
            if timeout > 0:
                await asyncio.wait_for(turn, timeout=timeout)
            else:
                await turn
        except TimeoutError:
            self.conversations.pop(context_id, None)
            logger.error(
                f"OpenHands回合超时[{context_id}] timeout={timeout}s，"
                "已丢弃该上下文会话"
            )
            return False
        except Exception as exc:
            logger.error(f"OpenHands回合失败[{context_id}]: {exc}")
            return False

        logger.info(f"openhands回合完成[{context_id}]")
        return True

    @staticmethod
    def _run_conversation_sync(conversation: Conversation, prompt: str) -> None:
        conversation.send_message(prompt)
        conversation.run()

    @staticmethod
    def _log_context_runner_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error(f"上下文处理任务失败: {exc}")

    @staticmethod
    def _summarize_batch_text(events: list[IncomingEvent]) -> str:
        text = " | ".join(AgentCore._event_display_text(event) for event in events)
        return text[:500]

    @staticmethod
    def _build_batch_payload(
        context_id: str, events: list[IncomingEvent]
    ) -> dict[str, object]:
        lines = []
        for index, event in enumerate(events, start=1):
            lines.append(f"{index}. {AgentCore._event_display_text(event)}")

        return {
            "context_id": context_id,
            "event_count": len(events),
            "text": "\n".join(lines),
            "latest_event": events[-1].to_dict(),
            "events": [
                {
                    "index": index,
                    **event.to_dict(),
                }
                for index, event in enumerate(events, start=1)
            ],
            "instruction": (
                "You are receiving one or more buffered events from the same context_id. "
                "Read them in order and answer the latest actionable intent. For OneBot QQ "
                "messages, use payload.raw from the relevant event as the qq_send_text target "
                "source. Usually send at most one concise QQ reply for the whole batch, then "
                "finish with DONE."
            ),
        }

    @staticmethod
    def _event_display_text(event: IncomingEvent) -> str:
        raw = event.raw
        sender = raw.get("sender")
        display_name = ""
        if isinstance(sender, dict):
            display_name = (
                str(sender.get("card") or sender.get("nickname") or "").strip()
            )
        if not display_name:
            display_name = str(raw.get("user_id") or event.context_id)

        text = event.text
        if not text:
            text = f"[{event.event_type}]"
        return f"{display_name}: {text}"

    async def list_contexts(self) -> list[dict[str, Any]]:
        async with self._contexts_lock:
            self._cleanup_contexts_locked()
            return [
                {
                    "context_id": context_id,
                    "busy": state.busy,
                    "buffer_size": len(state.buffer),
                    "last_active_at": state.last_active_at,
                    "message_count": state.message_count,
                    "has_conversation": context_id in self.conversations,
                }
                for context_id, state in sorted(self.contexts.items())
            ]

    async def close_context(self, context_id: str) -> bool:
        state = self.contexts.get(context_id)
        if state is None:
            self.conversations.pop(context_id, None)
            return False

        async with state.lock:
            state.buffer.clear()
            state.close_requested = True
            self.conversations.pop(context_id, None)
            if state.busy:
                return True

        await self._remove_context(context_id)
        return True

    async def reset_context(self, context_id: str) -> bool:
        return await self.close_context(context_id)

    async def _remove_context(self, context_id: str) -> None:
        async with self._contexts_lock:
            self.contexts.pop(context_id, None)
            self.conversations.pop(context_id, None)
        logger.info(f"关闭上下文[{context_id}]")


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


def _bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"1", "true", "yes", "on"}:
            return True
        if clean in {"0", "false", "no", "off"}:
            return False
    return bool(value)
