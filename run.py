import asyncio

from src.ws import WS
from src.agent import AgentCore
from src.bot.logger import register_logger
from src.bot.config import global_config

logger = register_logger('main',global_config.log_level)

async def main(ws:WS):
    agent = AgentCore(ws=ws)
    agent.ws.message_handler = agent.handle_message
    await agent.ws.connect()
    if agent.ws.role == 'client':
        while True:
            res = await agent.ws.recv()
            if res:
                await agent.handle_message(res)
    else:
        await asyncio.Future()

if __name__ == '__main__':
    ws = WS(
        host=global_config.ws_settings['host'],
        port=global_config.ws_settings['port'],
        role=global_config.ws_settings.get('role', 'client'),
    )
    logger.info('监听进程启动')
    asyncio.run(main(ws))
