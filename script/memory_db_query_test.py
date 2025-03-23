import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import numpy as np
import faiss

from src.bot.database import Database
from src.bot.llmapi import LLMAPI
from src.bot.config import global_config
from src.bot.logger import register_logger

logger = register_logger("memory")

class MemoryPiece:
    def __init__(self, summary: str, keywords: list[str]):
        self.summary = summary
        self.keywords = keywords

class Memory():
    def __init__(self, dim=global_config.memory_config['embedding_dim'], query_faiss_k=global_config.memory_config['query_faiss_k'], reranking_k=global_config.memory_config['reranking_k']):
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['uri'])
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
            "pg_id":int
        }
        '''
        self.memory: list[dict] = []
        # 使用IndexFlatIP来计算内积（余弦相似度）
        self.index = faiss.IndexFlatIP(self.dim)  # 改为内积索引

    async def load_memory(self):
        logger.info("开始加载记忆库")
        async with self.lock:
            self.memory = self.db.find(global_config.memory_config['memory_table_name'])

        embeddings = []
        for m in self.memory:
            embedding = np.array(m['embedding'])
            # 归一化每个embedding，以便使用内积来计算余弦相似度
            normalized_embedding = embedding / np.linalg.norm(embedding)  # 归一化向量
            embeddings.append(normalized_embedding)
        embeddings = np.array(embeddings, dtype=np.float32)
        self.index.add(embeddings)

        logger.info("记忆库加载完成")

    def rerank(self, query: str, docs: list[str]) -> list[dict]:
        """
        在候选文档上执行重新排序
        """

        reranking_result = self.llm_api.send_request_rerank(query, docs, reranking_k=10)

        return reranking_result

    def recall(self, keywords: list[dict], summary: str) -> list[MemoryPiece]:
        """
        根据摘要更新并返回相关记忆（余弦相似度）
        """
        if summary == "":
            return {}

        query_embedding = self.llm_api.send_request_embedding(summary)
        # 归一化查询embedding
        query_embedding = query_embedding / np.linalg.norm(query_embedding)  # 归一化查询向量

        logger.info(f"查询与[{summary}]相关的{self.query_faiss_k}条记忆")

        # Step 1: 执行初步的 FAISS 查询，获取最相似的记忆
        _, indices = self.index.search(query_embedding.reshape(1, -1), self.query_faiss_k)
        indices = indices[0]
        reranking_result = self.rerank(summary, [self.memory[i]['summary'] for i in indices])
        for i in reranking_result:
            logger.info(f"[{self.memory[indices[i['index']]]['summary']}]:[{i['relevance_score']}]")
        
async def main():
    memory = Memory()
    await memory.load_memory()
    query = "熬夜写代码不仅容易掉头发，还影响效率。"
    memory.recall([],query)

if __name__ == "__main__":
    asyncio.run(main())
