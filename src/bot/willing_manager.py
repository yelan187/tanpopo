import asyncio

from .logger import register_logger

logger = register_logger("willing_manager")

class WillingManager:
    def __init__(self):
        self.current_willing = 0.5  # 当前回复意愿
        self.started = False  # 是否已启动
        self.task = None  # 异步任务
        self.lock = asyncio.Lock()  # 用于线程安全的锁

    async def regress_willing(self):
        """
        独立运行的异步任务，定期衰减回复意愿。
        """
        while True:
            await asyncio.sleep(10)  # 每 10 秒更新一次
            async with self.lock:  # 确保线程安全
                self.current_willing += (0.4 - self.current_willing) / 10
                logger.debug(f"当前回复意愿 -> {self.current_willing:.2f}")

    async def start_regression_task(self):
        """
        启动意愿回复的异步任务。
        """
        if not self.started:
            self.started = True
            self.task = asyncio.create_task(self.regress_willing())
            logger.info("意愿衰减任务已启动")

    async def get_current_willing(self):
        """
        获取当前回复意愿。

        :return: 当前回复意愿值
        """
        async with self.lock:  # 确保线程安全
            return self.current_willing
    
    async def change_willing_after_send(self):
        """
        事件触发后改变回复意愿。

        :param dicide_send: 是否发送消息
        """
        async with self.lock:  # 确保线程安全
            self.current_willing = max(0, self.current_willing - 0.3)
            logger.debug(f"回复意愿减少到 -> {self.current_willing:.2f}")