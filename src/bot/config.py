from dataclasses import dataclass
from datetime import timezone, timedelta

@dataclass
class Config:
    """
    bot全局配置
    """

    enabled_prompts = [
        "personal_information",        
        "time",
        "schedule",
        "chat_history",
        "current_msg",
        "memory",
        "basic",
    ]

    gpt_settings = {
        "api_key": "sk-phlbcwawejllfeldnbgxonvrpokfwoeahkdtfzzbjgekrafv",
        "base_url": "https://api.siliconflow.cn/v1",
        "chat_model": "deepseek-ai/DeepSeek-V3",
        "image_model": "Qwen/Qwen2-VL-72B-Instruct",
        "semantic_analysis_model": "Qwen/Qwen2-7B-Instruct",
        "embedding_model":"BAAI/bge-large-zh-v1.5",
        "reranking_model":"Pro/BAAI/bge-reranker-v2-m3",
        "stream": False,
    }

    bot_config = {
        "personality": "你是一个宅系少女，虽然喜欢打游戏和沉浸在二次元世界中，但并不完全依赖虚拟世界。虽然性格偏内向，但你并不排斥社交，偶尔会和朋友们一起去咖啡馆或者参加小型聚会。",
        "nickname": "N0thing",
    }

    group_talk_allowed = [
        244847198,
        1040847329,
    ]

    memory_config = {
        "memory_table_name": "memory",
        "build_interval": 60,
        "embedding_dim": 1024,
        "query_faiss_k": 10,
        "reranking_k": 3,
        "strength_delta": 0.1,
        "decrease_rate": 0.95,
        "keywords_num": 2,
        "compression_threshold": 0.9,
        "build_associate_num": 3,
        "forget_interval": 3600,
        "forget_threshold": 0.2,
        "recall_threshold": 0.2
    }

    memes_config = {
        "memes_table_name": "memes",
        "add_meme_probability": 0.5
    }

    database_config = {
        "uri": "mongodb://localhost:27017/",
        "database_name":"tanpopo"
    }
    
    message_revoke_interval = 300

    time_zone = timezone(timedelta(hours=+8))   # UTC+8
    log_level = "DEBUG"

global_config = Config()
