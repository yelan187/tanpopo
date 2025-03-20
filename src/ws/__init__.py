import websockets

class WS:
    def __init__(self, host, port, role='client', callback=None):
        self.host = host
        self.port = port
        self.role = role
        self.url = f"ws://{self.host}:{self.port}/"
        self.message_callback = callback
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
            if self.message_callback:
                return await self.message_callback(message)
    
    async def send(self, message):
        if self.ws:
            await self.ws.send(message)
    
    async def recv(self):
        if self.ws:
            message = await self.ws.recv()
            # print(message)
            if self.message_callback:
                return await self.message_callback(message)

    async def close(self):
        if self.ws:
            await self.ws.close()