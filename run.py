import asyncio

from src.ws import WS
from src.bot.bot import Bot
from src.event import MessageEvent
from src.bot.logger import register_logger

logger = register_logger('main')

async def main(bot: Bot):
    await bot.ws.connect()
    if bot.ws.role == 'client':
        while True:
            res = await bot.ws.recv()
            if res:
                await bot.handle_message(res)
                # await bot.ws.send_message_list(message_list)

if __name__ == '__main__':
    ws = WS(host='127.0.0.1', port=3001, role='client', callback=MessageEvent())
    
    bot = Bot(ws=ws)
    logger.info('监听进程启动')
    asyncio.run(main(bot))
