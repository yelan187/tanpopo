import os
import shutil

import yaml

from dataclasses import dataclass, field
from datetime import timezone, timedelta
from typing import List, Dict


@dataclass
class Config:
    """
    bot全局配置
    """

    ws_settings: Dict[str, str] = field(
        default_factory=lambda: {"host": "127.0.0.1", "port": 3001}
    )
    enabled_prompts: List[str] = field(
        default_factory=lambda: [
            "personal_information",
            "time",
            "chat_history",
            "current_msg",
            "memory",
            "actions",
            "basic",
        ]
    )
    llm_auth: Dict[str, str] = field(default_factory=dict)
    llm_models: Dict[str, str] = field(
        default_factory=lambda: {
            "chat_model": "deepseek-ai/DeepSeek-V3",
            "image_model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "semantic_analysis_model": "Qwen/Qwen2.5-32B-Instruct",
            "embedding_model": "BAAI/bge-large-zh-v1.5",
            "reranking_model": "Pro/BAAI/bge-reranker-v2-m3",
            "stream": False,
            "max_retrys":3,
        }
    )
    bot_config: Dict[str,str] = field(
        default_factory=lambda: {
            "personality": "你是一个大一学生，正在学习计算机科学，你性格不错，为人友善但有点腹黑",
            "nickname": "N0thing",
            "alias": [],
        }
    )
    group_talk_allowed: List[int] = field(default_factory=list)
    memory_config: Dict[str, any] = field(
        default_factory=lambda: {
            "memory_table_name": "memory",
            "build_interval": 60,
            "embedding_dim": 1024,
            "query_faiss_k": 10,
            "reranking_k": 3,
            "strength_delta": 0.1,
            "decrease_rate": 0.95,
            "keywords_num": 2,
            "compression_threshold": 0.9,
            "build_associate_num": 2,
            "forget_interval": 3600,
            "forget_threshold": 0.2,
            "recall_threshold": 0.6,
        }
    )
    memes_config: Dict[str, any] = field(
        default_factory=lambda: {
            "memes_table_name": "memes",
            "add_meme_probability": 0.5,
        }
    )
    database_config: Dict[str, str] = field(
        default_factory=lambda: {
            "uri": "mongodb://localhost:27017/",
            "database_name": "tanpopo",
        }
    )
    bot_actions_enabled: List[str] = field(
        default_factory=lambda: ["艾特发送者", "发送表情包"]
    )
    
    message_revoke_interval: int = 300
    time_zone: timezone = timezone(timedelta(hours=+8))  # UTC+8
    log_level: str = "INFO"

    @staticmethod
    def from_yaml():
        """从YAML文件读取配置并加载到Config类实例中"""
        script_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前脚本所在的绝对路径
        project_root = os.path.abspath(os.path.join(script_dir, "../.."))
        # 构建绝对路径
        yaml_file = os.path.join(project_root, "config.yaml")
        config_template_path = os.path.join(project_root, "template", "config_template.yaml")
        if not os.path.exists(yaml_file):
            # 如果配置文件不存在，从template文件夹复制配置文件
            shutil.copy(config_template_path, yaml_file)
            raise FileNotFoundError("配置文件不存在，已从template文件夹复制默认配置文件，请完善llm_auth等配置。")

        # 读取配置文件
        with open(yaml_file, "r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file)

        # 创建Config实例
        config = Config()

        required_fields = ["llm_auth", "group_talk_allowed"]

        # 检查必需字段是否存在
        for field_name in required_fields:
            if field_name not in config_data:
                raise ValueError(f"配置文件中缺少必需字段: {field_name}")
        # 从YAML数据更新各个字段
        for field_name, field_value in config_data.items():
            if hasattr(config, field_name):
                field_type = type(getattr(config, field_name))

                # 对字段进行类型转换
                if field_type == list:
                    setattr(
                        config,
                        field_name,
                        field_value if isinstance(field_value, list) else [],
                    )
                elif field_type == dict:
                    setattr(
                        config,
                        field_name,
                        field_value if isinstance(field_value, dict) else {},
                    )
                else:
                    setattr(config, field_name, field_value)

        return config


global_config = Config.from_yaml()

# 如果环境是 DOCKER，可以更新配置
if os.getenv("ENV") == "DOCKER":
    global_config.ws_settings["host"] = "napcat"
    global_config.database_config["uri"] = "mongodb://mongodb:27017/"
    print("Using docker config")
