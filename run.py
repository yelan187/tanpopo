import asyncio

from src.ws import WS
from src.bot.bot import Bot
from src.bot.logger import register_logger
from src.bot.config import global_config

logger = register_logger('main',global_config.log_level)

async def main(ws:WS):
    bot = Bot(ws=ws)
    await bot.ws.connect()
    if bot.ws.role == 'client':
        while True:
            res = await bot.ws.recv()
            if res:
                await bot.handle_message(res)

if __name__ == '__main__':
    ws = WS(host=global_config.ws_settings['host'], port=global_config.ws_settings['port'], role='client')
    logger.info('监听进程启动')
    asyncio.run(main(ws))
