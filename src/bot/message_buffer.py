from collections import deque
import asyncio

from ..event import MessageEvent
from .logger import register_logger
from .config import global_config

logger = register_logger("message manager")

class MessageManager:
    def __init__(self, max_size: int=10):
        self.max_size = max_size  # 每个群聊消息缓存的最大容量
        self.started = False
        self.task = None
        self.lock = asyncio.Lock()
        self.message_revoke_interval = global_config.message_revoke_interval
        self.group_buffers: dict[int, deque] = {}  # 存储不同群聊的消息缓存
        self.private_buffers: dict[int, deque] = {}  # 存储不同私聊的消息缓存

    async def revoke_message_task(self):
        while True:
            await asyncio.sleep(self.message_revoke_interval)
            async with self.lock:
                for buffer in self.group_buffers.values():
                    if buffer:
                        buffer.popleft()
            async with self.lock:
                for buffer in self.private_buffers.values():
                    if buffer:
                        buffer.popleft()

    async def start_task(self):
        if not self.started:
            self.task = asyncio.create_task(self.revoke_message_task())
            self.started = True
            logger.info("消息缓存清理任务启动")

    async def push_message(self,idd: int,is_private:bool, message: MessageEvent):
        """向指定群聊/私聊添加一条消息"""
        logger.debug(f"消息添加到 {idd}: {message.get_plaintext()}")
        if is_private:
            async with self.lock:
                if idd not in self.private_buffers:
                    self.private_buffers[idd] = deque(maxlen=self.max_size)
                self.private_buffers[idd].append(message)
        else:
            async with self.lock:
                if idd not in self.group_buffers:
                    self.group_buffers[idd] = deque(maxlen=self.max_size)
                self.group_buffers[idd].append(message)

    async def get_all_messages(self,idd: int,is_private:bool) -> list[MessageEvent]:
        """获取指定群聊/私聊缓存的所有消息"""
        if is_private:
            async with self.lock:
                if idd in self.private_buffers:
                    return self.private_buffers[idd]
        else:
            async with self.lock:
                if idd in self.group_buffers:
                    return self.group_buffers[idd]
        return []