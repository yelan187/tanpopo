import asyncio
import logging
import os
import warnings

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
os.environ.setdefault("FASTMCP_LOG_LEVEL", "ERROR")
warnings.filterwarnings(
    "ignore",
    message="authlib\\.jose module is deprecated.*",
    category=Warning,
)
_default_showwarning = warnings.showwarning


def _showwarning(message, category, filename, lineno, file=None, line=None):
    if "authlib.jose module is deprecated" in str(message):
        return
    _default_showwarning(message, category, filename, lineno, file=file, line=line)


warnings.showwarning = _showwarning

NOISY_LOGGERS = ("openhands", "fastmcp", "mcp", "litellm", "LiteLLM")


def _set_noisy_log_level(level: int) -> None:
    for noisy_logger in NOISY_LOGGERS:
        logging.getLogger(noisy_logger).setLevel(level)


_set_noisy_log_level(logging.ERROR)

import uvicorn

from src.adapters import OneBotWebhookAdapter
from src.agent import AgentCore
from src.core import create_app
from src.runtime import global_config, register_logger
from src.ws import WS


logger = register_logger("main", global_config.log_level)
if bool(global_config.agent_config.get("openhands", {}).get("debug_trace", False)):
    _set_noisy_log_level(logging.INFO)
else:
    _set_noisy_log_level(logging.ERROR)


async def main():
    agent = AgentCore()
    app = create_app(agent)
    core_settings = global_config.core_settings
    core_host = str(core_settings.get("host", "127.0.0.1"))
    core_port = int(core_settings.get("port", 8080))
    adapter_endpoint = _core_adapter_endpoint(core_settings)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=core_host,
            port=core_port,
            log_level=str(global_config.log_level).lower(),
            access_log=False,
        )
    )
    server_task = asyncio.create_task(server.serve())
    for _ in range(50):
        if server.started:
            break
        if server_task.done():
            server_task.result()
        await asyncio.sleep(0.1)
    if not server.started:
        raise RuntimeError("Core HTTP server failed to start")

    ws = WS(
        host=global_config.ws_settings["host"],
        port=global_config.ws_settings["port"],
        role=global_config.ws_settings.get("role", "client"),
    )
    adapter = OneBotWebhookAdapter(adapter_endpoint)
    ws.message_handler = adapter.handle_message
    await ws.connect()
    await agent.prewarm()

    try:
        if ws.role == "client":
            while True:
                res = await ws.recv()
                if res:
                    ws._dispatch_message(res)
        else:
            await asyncio.Future()
    finally:
        await ws.close()
        server.should_exit = True
        await server_task


def _core_adapter_endpoint(core_settings: dict[str, object]) -> str:
    endpoint = str(core_settings.get("adapter_endpoint", "")).strip()
    if endpoint:
        return endpoint.rstrip("/") + "/v1/adapter/message"

    host = str(core_settings.get("adapter_host", "")).strip()
    if not host:
        bind_host = str(core_settings.get("host", "127.0.0.1")).strip()
        host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
    port = int(core_settings.get("port", 8080))
    return f"http://{host}:{port}/v1/adapter/message"


if __name__ == "__main__":
    logger.info("监听进程启动")
    asyncio.run(main())
