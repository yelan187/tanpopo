import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosed

from ..event import MessageEvent
from ..runtime import global_config, register_logger

logger = register_logger("ws", global_config.log_level)


class WS:
    def __init__(self, host, port, role="client"):
        self.host = host
        self.port = port
        self.role = role
        self.url = f"ws://{self.host}:{self.port}/"
        self.ws = None
        self.server = None
        self.message_handler = None

    async def connect(self):
        if self.role == "client":
            self.ws = await websockets.connect(self.url, ping_interval=6000, ping_timeout=3000)
        elif self.role == "server":
            self.server = await websockets.serve(
                self.on_message,
                "0.0.0.0",
                self.port,
                ping_interval=6000,
                ping_timeout=3000,
            )

    async def on_message(self, websocket):
        self.ws = websocket
        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError as exc:
                    logger.warning(f"忽略无效WS消息: {exc}")
                    continue

                if not isinstance(payload, dict):
                    logger.warning("忽略非JSON对象WS消息")
                    continue

                if payload.get("post_type") != "message":
                    continue
                if self.message_handler:
                    self._dispatch_message(MessageEvent(payload))
        except ConnectionClosed as exc:
            logger.info(f"WS连接关闭: code={exc.code}, reason={exc.reason}")
        except Exception as exc:
            logger.error(f"WS消息处理失败: {exc}")
        finally:
            if self.ws is websocket:
                self.ws = None

    async def send(self, message):
        if self.ws:
            await self.ws.send(message)

    async def recv(self):
        if self.ws:
            raw_message = await self.ws.recv()
            message = json.loads(raw_message)
            if message.get("post_type") != "message":
                return None
            return MessageEvent(message)
        return None

    def _dispatch_message(self, message_event: MessageEvent):
        task = asyncio.create_task(self.message_handler(message_event))
        task.add_done_callback(self._log_handler_result)
        return task

    @staticmethod
    def _log_handler_result(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error(f"WS消息处理任务失败: {exc}")

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
