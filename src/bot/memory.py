from datetime import datetime

import asyncio
import numpy as np
import faiss

from .database import Database
from .llmapi import LLMAPI
from .config import global_config
from .logger import register_logger

logger = register_logger("memory")

class MemoryPiece:
    def __init__(self,summary:str,keywords:list[str]):
        self.summary = summary
        self.keywords = keywords
class Memory():
    def __init__(self,bot,dim=global_config.memory_config['embedding_dim'],query_faiss_k=global_config.memory_config['query_faiss_k'],reranking_k=global_config.memory_config['reranking_k']):
        from .bot import Bot
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['url'])
        self.bot:Bot = bot
        self.started = False
        self.task = None
        self.lock = asyncio.Lock()
        self.llm_api = LLMAPI(global_config.gpt_settings)
        self.dim = dim
        self.query_faiss_k = query_faiss_k
        self.reranking_k = reranking_k
        '''
        memory_item = {
            "_id":int,
            "summary":str,
            "embedding":list[float],
            "keywords":list[str],
            "create_time":int,
            "last_access_time":int,
            "strength":float,
            "is_private":bool,
            "pg_id":int,
            "associates":list[int]
        }
        '''
        self.memory:list[dict] = []
        self.index = faiss.IndexFlatL2(self.dim)

    async def load_memory(self):
        logger.info("开始加载记忆库")
        async with self.lock:
            self.memory = self.db.find(global_config.memory_config['memory_table_name'])
        
        embeddings = []
        for m in self.memory:
            embedding = np.array(m['embedding'])
            embeddings.append(embedding)
        embeddings = np.array(embeddings)
        self.index.add(embeddings)

        logger.info("记忆库加载完成")

    async def build_memory(self):
        await self.load_memory()
        while True:
            for group_id in global_config.group_talk_allowed:

                chat_history = self.bot.message_manager.get_all_messages(group_id, False)
                if chat_history == []:
                    continue                
                current_message = chat_history[-1]

                analysis_result = self.llm_api.semantic_analysis(current_message, chat_history)
                self.recall(analysis_result['keywords'], analysis_result['summary'])

                new_summary = analysis_result['summary']
                new_keywords = analysis_result['keywords']
                new_embedding = self.llm_api.send_request_embedding(new_summary)  # 获取新记忆项的 embedding

                new_time = int(datetime.now(global_config.time_zone).timestamp())

                # 记忆项的元数据
                new_memory_item = {
                    "_id": len(self.memory) + 1,  # 假设通过自增 ID 来生成唯一标识
                    "summary": new_summary,
                    "embedding": new_embedding.tolist(),
                    "keywords": new_keywords,
                    "create_time": new_time,  # 使用当前时间戳
                    "last_access_time": new_time,
                    "strength": 1.0,  # 强度可以从一些其他逻辑来确定
                    "is_private": False,
                    "pg_id": current_message.get_id(),
                    "associates": []
                }

                self.db.insert(global_config.memory_config['memory_table_name'], new_memory_item)

                embedding_array = np.array(new_embedding, dtype=np.float32).reshape(1, -1)
                self.index.add(embedding_array)

                self.memory.append(new_memory_item)

                logger.info(f"成功添加新记忆: {new_memory_item['_id']} - {new_memory_item['summary']}")

            await asyncio.sleep(global_config.memory_config['build_interval'])


    async def start_building_task(self):
        '''
        加载记忆库,并启动记忆库更新任务
        '''
        if not self.started:
            self.started = True
            self.task = asyncio.create_task(self.build_memory())

    def recall(self,keywords:list[dict],summary:str) -> list[MemoryPiece]:
        """
        (目前只)根据摘要更新并返回相关记忆
        """
        if summary == "":
            return {}
        query_embedding = self.llm_api.send_request_embedding(summary)
        logger.info(f"查询与[{summary}]相关的{self.query_faiss_k}条记忆")
        distances, indices = self.index.search(query_embedding.reshape(1,-1),self.query_faiss_k)
        
        # logger.debug(f"查询结果: \n{indices}\n{distances}")

        return [MemoryPiece(self.memory[indices[0][i]]['summary'],self.memory[indices[0][i]]['keywords']) for i in range(len(distances[0]))]
    
'''
- 查询记忆: 

- 构建新记忆

- 更新强度

- 压缩记忆

- 联想

- 构建联想边
'''