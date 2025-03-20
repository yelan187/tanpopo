from ...event import MessageEvent

class Memory():
    def __init__(self):
        pass

    def recall(self, messageEvent: MessageEvent) -> dict[str,list[str]]:
        """
        更新记忆同时返回相关记忆
        Args:
            messageEvent (MessageEvent): 当前消息事件
        """
        return {}