from dataclasses import dataclass

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
        "stream": False,
    }

    bot_config = {
        "personality": "你是一个大一学生，正在学习计算机科学，你性格不错，为人友善但有点腹黑",
        "nickname": "N0thing",
    }

    group_talk_allowed = [
        # 244847198,
        1040847329,
    ]

    time_zone = +15   # UTC+8

    log_level = "DEBUG"

global_config = Config()
