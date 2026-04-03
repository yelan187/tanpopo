import sys
import os
from hashlib import md5
from datetime import datetime
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bot.database import Database
from src.bot.config import global_config
from src.bot.llmapi import LLMAPI

class Memory:
    def __init__(self):
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['uri'])
        self.llm_api = LLMAPI(global_config.llm_auth,global_config.llm_models)

    def insert_initial_memories(self):
        table_name = global_config.memory_config['memory_table_name']
        if self.db.find(table_name) != []:
            return
        self.db.delete_many(table_name, {})

        initial_memories = global_config.init_memory_config.get("initial_memories", [])

        cnt = 0
        for item in initial_memories:
            summary = item.get("summary", "").strip()
            keywords = item.get("keywords", [])
            if not summary:
                continue
            new_time = int(datetime.now(global_config.time_zone).timestamp())
            embedding = self.llm_api.send_request_embedding(summary)
            embedding = embedding / np.linalg.norm(embedding)  # 归一化嵌入向量
            new_memory_item = {
                "_id": cnt,  # 生成一个自增的 ID
                "summary": summary,
                "embedding": embedding.tolist(),  # 获取文本嵌入
                "keywords": keywords,
                "create_time": new_time,
                "strength": 1.0,
                "is_private": False,
                "pg_id": 0, # 假设属于群组 0
                "hash":md5(summary.encode()).hexdigest(),
                "associates":[]
            }
            
            cnt += 1
            self.db.insert(table_name, new_memory_item)
            print(f"成功插入新记忆: {new_memory_item['_id']} - {new_memory_item['summary']}")

# 创建并运行插入初始记忆的脚本
if __name__ == "__main__":
    memory = Memory()
    memory.insert_initial_memories()
