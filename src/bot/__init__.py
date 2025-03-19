import json

class Bot:

    def __init__(self, io):
        self.io = io

    async def send(self, message):
        message = {
            "action": "send_private_msg",
            "params": {
                "user_id":3061422023,
                "message":'aaa',
            }
        }
        message = json.dumps(message)
        print(message)
        await self.io.send(message)