import asyncio
from src.io import IO
from src.bot import Bot

from src.message import Message

async def main(bot: Bot):
    await bot.io.connect()

    if bot.io.role == 'client':
        while True:
            res = await bot.io.recv()
            if res:
                bot.handle_message(res)

if __name__ == '__main__':
    io = IO(host='127.0.0.1', port=3001, role='client', callback=Message())
    
    bot = Bot(io=io)

    asyncio.run(main(bot))
