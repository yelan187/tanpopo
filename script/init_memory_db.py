import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bot.database import Database
from src.bot.config import global_config
from src.bot.llmapi import LLMAPI

# 模拟 Memory 类，用于在数据库中插入记忆项
class Memory:
    def __init__(self):
        self.db = Database(global_config.database_config['database_name'], global_config.database_config['uri'])
        self.llm_api = LLMAPI(global_config.gpt_settings)

    def insert_initial_memories(self):
        self.db.delete_many(global_config.memory_config['memory_table_name'], {})

        initial_memories = [
            ("叶阑说自己不喜欢吃香菜", ["叶阑", "香菜"]),
            ("叶阑非常喜欢喝咖啡，尤其是拿铁", ["叶阑", "咖啡", "拿铁"]),
            ("叶阑偶尔会忘记自己的生日", ["叶阑", "生日"]),
            ("叶阑不喜欢养宠物", ["叶阑", "宠物"]),
            ("叶阑正在学习日语，每天都会花一些时间练习", ["叶阑", "日语", "学习"]),
            ("叶阑最近迷上了看科幻电影，最喜欢的电影是《星际穿越》", ["叶阑", "科幻电影", "星际穿越"]),
            ("叶阑有个旅行计划，计划明年去日本京都旅游", ["叶阑", "旅行", "日本", "京都"]),
            ("叶阑在前段时间工作中负责前端开发，最近正在使用 React 和 Vue 框架", ["叶阑", "前端开发", "React", "Vue"]),
            ("叶阑非常喜欢阅读心理学书籍，最近在看《影响力》", ["叶阑", "心理学", "影响力"]),
            ("叶阑周末喜欢去公园跑步，通常是早晨", ["叶阑", "公园", "跑步", "周末"]),
            ("叶阑喜欢吃辣，特别是麻辣火锅", ["叶阑", "辣", "麻辣火锅"]),
            ("叶阑在一次旅行中爬过黄山，觉得景色非常壮丽", ["叶阑", "黄山", "旅行", "爬山"]),
            ("叶阑正在做一份有关人工智能的研究，特别关注深度学习", ["叶阑", "人工智能", "深度学习"]),
            ("叶阑擅长运动,曾在校运动会的接力赛中获奖", ["叶阑", "运动会", "接力"]),
            ("叶阑不喜欢旅行,她更喜欢在家附近散步", ["叶阑", "旅行"]),
            ("叶阑小时候,每天晚上都会花一些时间做冥想，帮助自己放松", ["叶阑", "冥想", "放松", "晚上"]),
            ("叶阑最近在学习绘画,她正在尝试漫画", ["叶阑", "绘画", "漫画"]),
            ("叶阑不喜欢历史政治相关科目,她更喜欢科学", ["叶阑", "历史政治", "科学"]),
            ("叶阑喜欢动漫,她小时候经常看名侦探柯南", ["叶阑", "动漫", "名侦探柯南"]),
            ("叶阑擅长 CTF 网络安全竞赛,曾获得过许多奖项", ["叶阑", "CTF", "网络安全竞赛"]),
        ]


        # 插入到数据库中
        cnt = 0
        for summary, keywords in initial_memories:
            new_time = int(datetime.now(global_config.time_zone).timestamp())
            new_memory_item = {
                "_id": cnt,  # 生成一个自增的 ID
                "summary": summary,
                "embedding": self.llm_api.send_request_embedding(summary).tolist(),  # 如果需要可以留空，或者使用随机向量
                "keywords": keywords,
                "create_time": new_time,
                "last_access_time": new_time,
                "strength": 1.0,
                "is_private": False,
                "pg_id": 0  # 假设属于群组 0
            }
            cnt += 1
            self.db.insert(global_config.memory_config['memory_table_name'], new_memory_item)
            print(f"成功插入新记忆: {new_memory_item['_id']} - {new_memory_item['summary']}")

# 创建并运行插入初始记忆的脚本

if __name__ == "__main__":
    memory = Memory()
    memory.insert_initial_memories()
