import asyncio
import json

class MessageQueue:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def put(self, message):
        message = json.loads(message)

        # 仅处理消息
        if message['post_type'] == 'message':
            print(message['post_type'])
            await self.queue.put(message)

    async def get(self):
        message = await self.queue.get()
        return message

    def size(self):
        return self.queue.qsize()