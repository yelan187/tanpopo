from ..event import MessageEvent

from collections import deque

class MessageManager:
    def __init__(self, max_size: int=10):
        self.max_size = max_size  # 每个群聊消息缓存的最大容量
        self.group_buffers: dict[int, deque] = {}  # 存储不同群聊的消息缓存
        self.private_buffers: dict[int, deque] = {}  # 存储不同私聊的消息缓存

    def push_message(self,id: int,is_private:bool, message: MessageEvent):
        """向指定群聊/私聊添加一条消息"""
        if is_private:
            if id not in self.private_buffers:
                self.private_buffers[id] = deque(maxlen=self.max_size)
            self.private_buffers[id].append(message)
        else:
            if id not in self.group_buffers:
                self.group_buffers[id] = deque(maxlen=self.max_size)
            self.group_buffers[id].append(message)

    def get_all_messages(self,id: str,is_private:bool) -> list[MessageEvent]:
        """获取指定群聊/私聊缓存的所有消息"""
        if is_private:
            if id in self.private_buffers:
                return self.private_buffers[id]
        else:
            if id in self.group_buffers:
                return self.group_buffers[id]
        return []