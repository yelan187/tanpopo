import asyncio

from .logger import register_logger
from ..event import MessageEvent
from .config import global_config

logger = register_logger("willing manager",global_config.log_level)


class WillingManager:
    def __init__(self):
        self.current_willing: dict[int, float] = {}  # 当前回复意愿
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
                for idd in self.current_willing.keys():
                    self.current_willing[idd] += (0.5 - self.current_willing[idd]) / 10

    async def start_regression_task(self):
        """
        启动意愿回复的异步任务。
        """
        if not self.started:
            self.started = True
            self.task = asyncio.create_task(self.regress_willing())
            logger.info("意愿衰减任务已启动")

    async def get_current_willing(self, idd: int):
        """
        获取当前回复意愿。
        Args
            idd: 用户ID
        return: 当前回复意愿值
        """
        async with self.lock:  # 确保线程安全
            willing = self.current_willing[idd]
            logger.debug(f"当前群{idd}的回复意愿为{willing}")
            return willing

    async def change_willing_after_send(self, idd: int,send:bool):
        """
        事件触发后改变回复意愿。

        :param dicide_send: 是否发送消息
        """
        async with self.lock:  # 确保线程安全
            if send:
                self.current_willing[idd] = max(0, self.current_willing[idd] - 0.1)

    async def change_willing_after_receive(self, message: MessageEvent):
        """
        事件触发后改变回复意愿。
        """
        if message.is_tome:
            increase = 0.5
        elif global_config.bot_config["nickname"] in message.get_plaintext():
            increase = 0.2
        else:
            for name in global_config.bot_config["alias"]:
                if name in message.get_plaintext():
                    increase = 0.2
                    break
            increase = 0
    
        idd = message.group_id if message.is_group() else message.user_id
        async with self.lock:  # 确保线程安全
            if self.current_willing.get(idd,None) is None:
                self.current_willing[idd] = 0.5
            self.current_willing[idd] = min(1, self.current_willing[idd] + increase)
            willing = self.current_willing[idd]
            logger.debug(f"当前群{idd}的回复意愿为{willing}")
            return willing
        
    async def change_willing_if_thinking(self,idd):
        async with self.lock:
            self.current_willing[idd] = max(0, self.current_willing[idd] - 0.4)
