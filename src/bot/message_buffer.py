from ..event import MessageEvent

class MessageBuffer:
    def __init__(self, max_size: int):
        self.max_size = max_size  # 消息缓存的最大容量
        self.buffer: list[MessageEvent] = []

    def push_message(self, message: MessageEvent):
        """添加一条消息，如果超过最大容量，则移除最早的消息"""
        if len(self.buffer) >= self.max_size:
            self.buffer.pop(0)  # 移除最早的消息
        self.buffer.append(message)  # 添加新消息

    def get_all(self) -> list[MessageEvent]:
        """返回按时间排序的消息列表"""
        return self.buffer

class MessageManager:
    def __init__(self, max_size: int=10):
        self.max_size = max_size  # 每个群聊消息缓存的最大容量
        self.group_buffers: dict[int, MessageBuffer] = {}  # 存储不同群聊的消息缓存
        self.private_buffers: dict[int, MessageBuffer] = {}  # 存储不同私聊的消息缓存

    def push_message(self,id: int,is_private:bool, message: MessageEvent):
        """向指定群聊/私聊添加一条消息"""
        if is_private:
            if id not in self.private_buffers:
                self.private_buffers[id] = MessageBuffer(self.max_size)
            self.private_buffers[id].push_message(message)
        else:
            if id not in self.group_buffers:
                self.group_buffers[id] = MessageBuffer(self.max_size)
            self.group_buffers[id].push_message(message)

    def get_all_messages(self,id: str,is_private:bool) -> list[MessageEvent]:
        """获取指定群聊/私聊缓存的所有消息"""
        if is_private:
            if id in self.private_buffers:
                return self.private_buffers[id].get_all()
        else:
            if id in self.group_buffers:
                return self.group_buffers[id].get_all()
        return []