import asyncio
import json
import os
import sys
from pathlib import Path

from openhands.sdk import Agent, Conversation, LLM, Tool

from ..bot.config import global_config
from ..bot.logger import register_logger
from ..event import MessageEvent
from ..ws import WS


logger = register_logger("agent", global_config.log_level)


class AgentCore:
    def __init__(self, ws: WS):
        self.ws = ws
        self.workspace_root = Path.cwd().resolve()

        self.locks: dict[str, asyncio.Lock] = {}
        self.conversations: dict[str, Conversation] = {}

        self.llm = self._build_llm()
        self.agent = self._build_agent()

    def _build_llm(self) -> LLM:
        openhands_config = global_config.agent_config.get("openhands", {})
        model = (
            os.getenv("LLM_MODEL")
            or str(openhands_config.get("model", "")).strip()
            or global_config.llm_models.get("chat_model", "")
        )
        api_key = os.getenv("LLM_API_KEY") or global_config.llm_auth.get("api_key")
        base_url = os.getenv("LLM_BASE_URL") or global_config.llm_auth.get("base_url")
        return LLM(model=model, api_key=api_key, base_url=base_url)

    def _build_agent(self) -> Agent:
        openhands_config = global_config.agent_config.get("openhands", {})
        qqio_mcp = openhands_config.get("qqio_mcp", {})

        command = str(qqio_mcp.get("command", "")).strip() or sys.executable
        args = qqio_mcp.get("args")
        if not isinstance(args, list) or not args:
            args = ["-m", "src.agent.qqio_mcp"]

        cwd = str(qqio_mcp.get("cwd", "")).strip() or str(self.workspace_root)
        mcp_config = {
            "mcpServers": {
                "qqio": {
                    "transport": "stdio",
                    "command": command,
                    "args": args,
                    "cwd": cwd,
                    "env": {
                        "TANPOPO_HTTP_HOST": str(global_config.http_settings.get("host", "127.0.0.1")),
                        "TANPOPO_HTTP_PORT": str(global_config.http_settings.get("port", 3000)),
                        "TANPOPO_MEMORY_FILE": str(self.workspace_root / "tmp" / "agent_memories.jsonl"),
                    },
                }
            }
        }

        return Agent(
            llm=self.llm,
            tools=[
                Tool(name="terminal"),
                Tool(name="file_editor"),
                Tool(name="task_tracker"),
            ],
            mcp_config=mcp_config,
        )

    def _get_session_id(self, message_event: MessageEvent) -> str:
        if message_event.is_group():
            return f"group:{message_event.group_id}"
        return f"private:{message_event.user_id}"

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

        openhands_config = global_config.agent_config.get("openhands", {})
        workspace = str(openhands_config.get("workspace", "")).strip() or str(self.workspace_root)
        conversation = Conversation(agent=self.agent, workspace=workspace)
        self.conversations[session_id] = conversation
        return conversation

    async def handle_message(self, message_event: MessageEvent) -> None:
        session_id = self._get_session_id(message_event)
        async with self._get_session_lock(session_id):
            await self._run_openhands_agent_loop(message_event, session_id)

    async def _run_openhands_agent_loop(self, message_event: MessageEvent, session_id: str) -> None:
        text = message_event.get_plaintext(with_at=True).strip()
        logger.info(f"openhands收到消息[{session_id}] -> {text}")
        if not text:
            logger.debug("空消息，跳过")
            return

        conversation = self._get_or_create_conversation(session_id)
        prompt = json.dumps(
            {
                "session_id": session_id,
                "message_type": message_event.message_type,
                "group_id": message_event.group_id,
                "user_id": message_event.user_id,
                "sender_nickname": getattr(message_event.sender, "nickname", ""),
                "sender_card": getattr(message_event.sender, "card", ""),
                "message_id": message_event.message_id,
                "text": text,
                "instruction": (
                    "You are a QQ chat agent. Reply by calling MCP tool qq_send_text. "
                    "Do not output plain text as final answer. "
                    "If needed, store long-term notes via MCP tool memory_append."
                ),
            },
            ensure_ascii=False,
        )

        await asyncio.to_thread(conversation.send_message, prompt)
        await asyncio.to_thread(conversation.run)
        logger.info(f"openhands回合完成[{session_id}]")
