import asyncio
import numpy as np
import faiss

from ..database import Database
from ..llmapi import llmApi
from ..config import global_config
from ..logger import register_logger

logger = register_logger("memory")

class Memory():
    def __init__(self):
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['uri'])
        self.started = False
        self.task = None
        self.lock = asyncio.Lock()
        self.llm_api = llmApi(global_config.gpt_settings)
        '''
        memory_item = {
            "_id":str,
            "summary":str,
            "embedding":np.array,
            "keywords":list[str],
            "create_time":int,
            "last_access_time":int
        }
        '''
        self.memory:list[dict] = []

    async def load_memory(self):
        logger.info("开始加载记忆库")
        async with self.lock():
            self.memory = self.db.find(global_config.memory_config['memory_table_name'])
        logger.info("记忆库加载完成")

    async def build_memory(self):
        await self.load_memory()
        while True:
            await asyncio.sleep(600)

    async def start_building_task(self):
        '''
        加载记忆库,并启动记忆库更新任务
        '''
        if not self.started:
            self.started = True
            self.task = asyncio.create_task(self.build_memory())

    def recall(self,keywords:list[str],summary:str) -> dict[str,list[str]]:
        """
        (目前只)根据摘要更新并返回相关记忆
        """
        if summary == "":
            return {}
        embedding = self.llm_api.send_request_embedding(summary)