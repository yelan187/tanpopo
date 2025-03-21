import websockets
import json
from ..event import MessageEvent

class WS:
    def __init__(self, host, port, role='client'):
        self.host = host
        self.port = port
        self.role = role
        self.url = f"ws://{self.host}:{self.port}/"
        self.ws = None

    async def connect(self):
        if self.role == 'client':
            self.ws = await websockets.connect(self.url)
            # print(f"Client connected to {self.url}")
        elif self.role == 'server':
            self.ws = await websockets.serve(self.on_message, '0.0.0.0', self.port)
            # print(f"Server started at {self.url}")

    async def on_message(self, websocket):
        async for message in websocket:
            message = json.loads(message)
            if message.get('post_type') != 'message':
                return None
            return MessageEvent(message)

    async def send(self, message):
        if self.ws:
            await self.ws.send(message)
    
    async def recv(self):
        if self.ws:
            message = await self.ws.recv()
            message = json.loads(message)
            if message.get('post_type') != 'message':
                return None
            return MessageEvent(message)
        
    async def close(self):
        if self.ws:
            await self.ws.close()