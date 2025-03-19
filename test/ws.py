import asyncio
import websockets

class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect(self.url)
        print(f"Connected to {self.url}")
    
    async def send(self, message):
        if self.ws:
            await self.ws.send(message)
            print(f"Sent: {message}")
    
    async def recv(self):
        if self.ws:
            message = await self.ws.recv()
            print(f"Received: {message}")
            return message
    
    async def close(self):
        if self.ws:
            await self.ws.close()
            print("Connection closed.")

    async def start(self):
        await self.connect()
        while True:
            message = await self.receive_message()
            print(f"Processed: {message}")


async def main():
    robot_ws = WebSocketClient("ws://127.0.0.1:3001/")
    await robot_ws.start()  # 启动机器人

# 运行异步事件循环
if __name__ == "__main__":
    asyncio.run(main())
