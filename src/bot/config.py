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
    http_settings: Dict[str, str] = field(
        default_factory=lambda: {"host": "127.0.0.1", "port": 3000}
    )
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
    init_memory_config: Dict[str, any] = field(
        default_factory=lambda: {
            "initial_memories": [
                {
                    "summary": "Dremig喜欢吃的东西包括牛肉和禽肉，他也很喜欢吃青菜，包括香菜",
                    "keywords": ["Dremig", "牛肉", "禽肉", "青菜", "香菜"],
                },
                {
                    "summary": "Dremig认为留长头发就应该同时留胡子",
                    "keywords": ["Dremig", "长头发", "胡子"],
                },
                {
                    "summary": "Dremig喜欢吃辣的食物，但是他的口味除了辣之外其实偏清淡",
                    "keywords": ["Dremig", "辣", "清淡"],
                },
                {
                    "summary": "Dremig喜欢吃甜食和冰的东西，比如蛋挞和冰淇淋",
                    "keywords": ["Dremig", "甜食", "蛋挞", "冰淇淋"],
                },
                {
                    "summary": "Dremig高中时期曾经喜欢过一个很温柔也很善良的女孩",
                    "keywords": ["Dremig", "高中", "喜欢过", "女孩"],
                },
                {
                    "summary": "Dremig的专业是计算机科学与技术，但是他的主攻领域是网络空间安全",
                    "keywords": ["Dremig", "计算机科学与技术", "网络空间安全"],
                },
                {
                    "summary": "Dremig喜欢看动漫，尤其是恋爱轻喜剧",
                    "keywords": ["Dremig", "动漫", "恋爱轻喜剧"],
                },
                {
                    "summary": "Dremig喜欢听音乐，也喜欢听虚拟歌姬",
                    "keywords": ["Dremig", "音乐", "虚拟歌姬"],
                },
                {
                    "summary": "Dremig不喜欢在电影院里看电影，因为太暗了他会害怕",
                    "keywords": ["Dremig", "电影院", "电影", "害怕"],
                },
                {
                    "summary": "Dremig在ai方面也有一些兴趣与研究",
                    "keywords": ["Dremig", "AI", "研究"],
                },
                {
                    "summary": "Dremig比较喜欢玩fps类的游戏",
                    "keywords": ["Dremig", "FPS", "游戏"],
                },
                {
                    "summary": "Dremig在泰拉瑞亚方面相当厉害",
                    "keywords": ["Dremig", "泰拉瑞亚", "游戏"],
                },
                {
                    "summary": "Dremig喜欢玩galgame，甚至喜欢将自己喜欢的女主的名字作为自己的github仓库名",
                    "keywords": ["Dremig", "galgame", "GitHub", "女主"],
                },
                {
                    "summary": "Dremig最近才开始健身，每天都跑3-5公里",
                    "keywords": ["Dremig", "健身", "跑步"],
                },
                {
                    "summary": "Dremig每天都熬夜，他是坏孩子",
                    "keywords": ["Dremig", "熬夜"],
                },
                {
                    "summary": "Dremig基本不吃早餐，但每天都吃宵夜",
                    "keywords": ["Dremig", "早餐", "宵夜"],
                },
                {
                    "summary": "Dremig曾经担任过C语言和数据结构基础的助教",
                    "keywords": ["Dremig", "C语言", "数据结构", "助教"],
                },
                {
                    "summary": "Dremig英语水平曾经很高，但是现在很差，六级考了4次没过550分",
                    "keywords": ["Dremig", "英语", "六级"],
                },
                {
                    "summary": "Dremig最喜欢的gal女主角是在原七海",
                    "keywords": ["Dremig", "galgame", "在原七海"],
                },
                {
                    "summary": "Dremig现在在玉泉校区上课",
                    "keywords": ["Dremig", "玉泉校区", "上课"],
                },
            ]
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
        init_memory_yaml_file = os.path.join(project_root, "init_memory_config.yaml")
        init_memory_template_path = os.path.join(project_root, "template", "init_memory_config_template.yaml")
        if not os.path.exists(yaml_file):
            # 如果配置文件不存在，从template文件夹复制配置文件
            shutil.copy(config_template_path, yaml_file)
            raise FileNotFoundError("配置文件不存在，已从template文件夹复制默认配置文件，请完善llm_auth等配置。")

        # 读取配置文件
        with open(yaml_file, "r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file)

        if not os.path.exists(init_memory_yaml_file) and os.path.exists(init_memory_template_path):
            shutil.copy(init_memory_template_path, init_memory_yaml_file)

        init_memory_data = {}
        if os.path.exists(init_memory_yaml_file):
            with open(init_memory_yaml_file, "r", encoding="utf-8") as file:
                init_memory_data = yaml.safe_load(file) or {}

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

        # init memory 独立配置文件优先
        if isinstance(init_memory_data, dict):
            if isinstance(init_memory_data.get("initial_memories"), list):
                config.init_memory_config = {
                    "initial_memories": init_memory_data["initial_memories"]
                }
            elif (
                isinstance(init_memory_data.get("init_memory_config"), dict)
                and isinstance(
                    init_memory_data["init_memory_config"].get("initial_memories"), list
                )
            ):
                config.init_memory_config = {
                    "initial_memories": init_memory_data["init_memory_config"]["initial_memories"]
                }

        return config


global_config = Config.from_yaml()

# 如果环境是 DOCKER，可以更新配置
if os.getenv("ENV") == "DOCKER":
    global_config.ws_settings["host"] = "0.0.0.0"
    global_config.ws_settings["role"] = "server"
    global_config.http_settings["host"] = "napcat"
    global_config.database_config["uri"] = "mongodb://mongodb:27017/"
    print("Using docker config")
