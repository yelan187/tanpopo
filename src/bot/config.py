from dataclasses import dataclass

@dataclass
class Config:
    """
    bot全局配置
    """

    enabled_prompts = [
        "time",
        "personal_information",
        "chat_history",
        "current_msg",
        "basic",
    ]

    gpt_settings = {
        "api_key": "sk-phlbcwawejllfeldnbgxonvrpokfwoeahkdtfzzbjgekrafv",
        "base_url": "https://api.siliconflow.cn/v1",
        "chat_model": "deepseek-ai/DeepSeek-V3",
        "image_model": "Qwen/Qwen2-VL-72B-Instruct",
        "stream": False,
    }

    bot_config = {
        "personality": "你是一个大一学生，正在学习计算机科学，你性格不错，为人友善但有点腹黑",
        "nickname": "N0thing",
    }

global_config = Config()
