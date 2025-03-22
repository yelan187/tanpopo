from datetime import datetime
import random
from hashlib import md5

import asyncio
import numpy as np
import faiss

from .database import Database
from .llmapi import LLMAPI
from .config import global_config
from .logger import register_logger

logger = register_logger("memory")

class MemoryPiece:
    def __init__(self,memory_piece:dict,associate:bool):
        self.summary:str = memory_piece['summary']
        self.associate:bool = associate
        self.create_time:str = datetime.fromtimestamp(memory_piece['create_time']).strftime("%Y-%m-%d")

class Memory():
    def __init__(self,bot):
        from .bot import Bot
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['uri'])
        self.bot:Bot = bot
        self.biulding_started = False
        self.forgetting_started = False
        self.task = None
        self.lock = asyncio.Lock()
        self.llm_api = LLMAPI(global_config.gpt_settings)
        self.dim = global_config.memory_config['embedding_dim']
        self.query_faiss_k=global_config.memory_config['query_faiss_k']
        self.reranking_k=global_config.memory_config['reranking_k']
        self.strength_delta = global_config.memory_config['strength_delta']
        self.compression_threshold = global_config.memory_config['compression_threshold']
        self.table_name = global_config.memory_config['memory_table_name']
        self.build_interval = global_config.memory_config['build_interval']
        self.decrease_rate = global_config.memory_config['decrease_rate']
        self.forget_interval = global_config.memory_config['forget_interval']
        self.build_associate_num = global_config.memory_config['build_associate_num']
        self.forget_threshold = global_config.memory_config['forget_threshold']
        self.recall_threshold = global_config.memory_config['recall_threshold']
        '''
        memory_item = {
            "_id":int,  # 仅用于搜索
            "summary":str,
            "embedding":list[float],
            "keywords":list[str],
            "create_time":int,
            "strength":float,
            "is_private":bool,
            "pg_id":int,
            "associates":list[str],
            "hash":str  # 唯一标识
        }
        '''
        self.memory:list[dict] = []
        self.index = faiss.IndexFlatL2(self.dim)

    async def load_memory(self):
        logger.info("开始加载记忆库")
        async with self.lock:
            self.memory = self.db.find(self.table_name)
            self.memory.sort(key=lambda x: x['_id'])
        embeddings = []
        for m in self.memory:
            embedding = np.array(m['embedding'])
            embeddings.append(embedding)
        embeddings = np.array(embeddings)
        self.index.add(embeddings)
        logger.info("记忆库加载完成")


    async def forget_memory(self):
        while True:
            await asyncio.sleep(self.forget_interval)
            logger.info("开始记忆库遗忘")
            async with self.lock:
                for m in self.memory:
                    m['strength'] *= self.decrease_rate
                    self.db.update_one(self.table_name, {"hash": m['hash']}, {"$set": {"strength": m['strength']}})
                total_memory = len(self.memory)
                index = 0
                while index < total_memory:
                    if self.memory[index]['strength'] > self.forget_threshold:
                        index += 1
                    else:
                        logger.info(f"遗忘记忆 {self.memory[index]['summary']}")
                        self.memory[index] = self.memory[-1]
                        self.memory.pop()
                        self.memory[index]['_id'] = index
                        self.db.update_one(self.table_name, {"_id": index}, {"$set": self.memory[index]})
                        self.db.delete_one(self.table_name, {"_id": total_memory - 1})
                        total_memory -= 1
                embeddings = []
                for m in self.memory:
                    embedding = np.array(m['embedding'])
                    embeddings.append(embedding)
                embeddings = np.array(embeddings)
                self.index = faiss.IndexFlatL2(self.dim)
                self.index.add(embeddings)
                logger.info("记忆库遗忘完成")
                        
    async def start_forgetting_task(self):
        '''
        启动记忆库遗忘任务
        '''
        if not self.forgetting_started:
            self.starforgetting_startedted = True
            self.task = asyncio.create_task(self.forget_memory())

    async def build_memory(self):
        await self.load_memory()
        while True:
            await asyncio.sleep(self.build_interval)
            for group_id in global_config.group_talk_allowed:
                chat_history = await self.bot.message_manager.get_all_messages(group_id, False)
                if chat_history == []:
                    continue
                current_message = chat_history[-1]
                analysis_result = self.llm_api.semantic_analysis(current_message, chat_history)

                new_summary = analysis_result['summary']

                reranked_result, new_embedding = self.get_reranked_result(new_summary)
                
                logger.debug(reranked_result[0]['relevance_score'])
                if reranked_result[0]['relevance_score'] > self.compression_threshold:
                    logger.debug(f"记忆被压缩")
                    continue
                
                new_time = int(datetime.now(global_config.time_zone).timestamp())
                new_keywords = analysis_result['keywords']
                logger.info(f"添加新记忆: {new_summary} - {new_keywords}")
                new_memory_item = {
                    "_id": len(self.memory),
                    "summary": new_summary,
                    "embedding": new_embedding.tolist(),
                    "keywords": new_keywords,
                    "create_time": new_time,
                    "strength": 1.0,
                    "is_private": False,
                    "pg_id": current_message.get_id(),
                    "associates": [],
                    "hash": md5(new_summary.encode()).hexdigest()
                }

                associated_hashes:list[str] = [item['hash'] for item in self.db.find(self.table_name, {"keywords": {"$in": new_keywords}})]
                if associated_hashes == []:
                    pass
                else:
                    associated_hashes = random.sample(associated_hashes, min(len(associated_hashes), self.build_associate_num))
                    new_memory_item['associates'] = associated_hashes
                    for hash in associated_hashes:
                        self.db.update_one(self.table_name, {"hash": hash}, {"$push": {"associates": new_memory_item["hash"]}})
                        logger.debug(f"添加关联记忆: {self.db.find_one(self.table_name, {'hash': hash})['summary']}")

                self.memory.append(new_memory_item)
                self.index.add(np.array(new_embedding, dtype=np.float32).reshape(1, -1))
                self.db.insert(self.table_name, new_memory_item)

    async def start_building_task(self):
        '''
        加载记忆库,并启动记忆库更新任务
        '''
        if not self.biulding_started:
            self.biulding_started = True
            self.task = asyncio.create_task(self.build_memory())

    def get_reranked_result(self,summary:str,faiss_k=None,reranking_k=None) -> list:
        
        '''
        reranked_result = [
            {
                "index": 1, # **原记忆**中的索引
                "relevance_score": 0.9,
            },
            ...
        ]
        '''
        faiss_k = self.query_faiss_k if faiss_k is None else faiss_k
        reranking_k = self.reranking_k if reranking_k is None else reranking_k
        query_embedding:np.array = self.llm_api.send_request_embedding(summary)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        logger.info(f"查询与[{summary}]相关的{faiss_k}条记忆")
        _, indices = self.index.search(query_embedding.reshape(1,-1),faiss_k)

        doc_indexes = indices[0]
        reranked_result:list[dict] = self.llm_api.send_request_rerank(summary,[self.memory[i]['summary'] for i in doc_indexes], reranking_k)
        res = []
        for i in range(len(reranked_result)):
            reranked_result[i]["index"] = int(doc_indexes[i])
            res += [reranked_result[i]]
        return res,query_embedding

    async def update_memory_strength(self,_id:list[int],delta:float):
        for index in _id:
            self.memory[index]['strength'] += delta
            self.db.update_one(self.table_name, {"_id": index}, {"$set": {"strength": self.memory[index]['strength']}})

    def select_associated_memories(self,memories:list[dict],k=2) -> list[dict]:
        selected_items = random.choices(memories, weights=[i['strength'] for i in memories], k=k)
        return selected_items

    async def recall(self,summary:str) -> list[MemoryPiece]:
        """
        根据摘要更新并返回相关记忆
        """
        memory_pieces:list[MemoryPiece] = []
        
        if summary == "":
            return {}
        reranked_result,_ = self.get_reranked_result(summary)

        await self.update_memory_strength([i['index'] for i in reranked_result],self.strength_delta)
        filtered_reranked_result = [i for i in reranked_result if i['relevance_score'] > self.recall_threshold]
        if filtered_reranked_result == []:
            return []
        
        associates = []
        for i in filtered_reranked_result:
            associates += self.memory[i['index']]['associates']
        associates = list(set(associates))
        
        if associates != []:
            associated_memories:list[dict] = [self.db.find_one(self.table_name,{'hash':i}) for i in associates]
            associated_memories = self.select_associated_memories(associated_memories)
            memory_pieces += [MemoryPiece(i,associate=True) for i in associated_memories]
            await self.update_memory_strength([i['_id'] for i in associated_memories],self.strength_delta)

        memory_pieces += [MemoryPiece(self.memory[i['index']],associate=False) for i in reranked_result]
        return memory_pieces

'''
- 查询记忆: 相似度计算然后重排序,找到最相关的三条记忆,再根据这三条记忆的联想记忆找到联想度最强的两条记忆
    
    + 更新强度: 被查询且被选择到的记忆强度加某值

- 构建新记忆: 构建.并且根据关键词构建联想边

    + 如果发现和某条记忆的相似度超过阈值,则删除该记忆

- 遗忘: 每次 forget 的时候减少所有记忆的强度(防止数值膨胀),并删除强度低于阈值的记忆
'''