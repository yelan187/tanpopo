import asyncio
from src.io import IO
from src.queue import MessageQueue
from src.bot import Bot

async def main(io, bot, messageQueue):
    await io.start()
    
    while True:
        print(messageQueue.size())
        message = await messageQueue.get()
        await bot.send(message)

if __name__ == '__main__':
    messageQueue = MessageQueue()

    io = IO(host='127.0.0.1', port=3001, role='client', callback=messageQueue.put)

    bot = Bot(io=io)
    
    asyncio.run(main(io, bot, messageQueue))
