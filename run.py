import asyncio
from src.ws import WS
from src.bot import Bot

from src.event import MessageEvent

async def main(bot: Bot):
    await bot.io.connect()

    if bot.ws.role == 'client':
        while True:
            res = await bot.io.recv()
            if res:
                message_list: str = bot.handle_message(res)
                async for message in message_list:
                    await bot.io.send(message)

if __name__ == '__main__':
    ws = WS(host='127.0.0.1', port=3001, role='client', callback=MessageEvent())
    
    bot = Bot(ws=ws)

    asyncio.run(main(bot))
