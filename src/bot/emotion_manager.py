import asyncio
import random

from .logger import register_logger
from ..event import MessageEvent
from .config import global_config

logger = register_logger("emotion manager")

class EmotionManager:
    """
    VAD情感分析器（基于词典方法）
    示例词库数据来源：NRC VAD Lexicon (简化版)
    """
    def __init__(self,bot):
        from .bot import Bot
        self.vad_lexicon = {
            "快乐": (0.95, 0.80, 0.70),
            "悲伤": (0.10, 0.30, 0.20),
            "愤怒": (0.25, 0.95, 0.85),
            "惊喜": (0.85, 0.90, 0.60),
            "平静": (0.65, 0.20, 0.50),
            "恐惧": (0.30, 0.85, 0.30),
            "爱": (0.98, 0.60, 0.75),
            "讨厌": (0.15, 0.70, 0.65)
        }
        self.default_vad = (0.5, 0.5, 0.5)
        self.current_value = (0.5, 0.5, 0.5)
        self.decay_factor = 0.4    # 新情感影响权重
        self.decay_factor = 0.4    # 新情感影响权重
        self.inertia = 0.35         # 情感惯性系数（衰减任务）
        self.started = False
        self.task = None
        self.lock = asyncio.Lock()
        self.bot:Bot = bot

    async def regressing_emotion(self):
        """独立运行的异步任务，定期衰减VAD值"""
        while True:
            await asyncio.sleep(30)  # 每30秒更新一次
            await asyncio.sleep(30)  # 每30秒更新一次
            async with self.lock:
                # 线性衰减至中性值
                v = self.current_value[0] * self.inertia + 0.5 * (1 - self.inertia)
                a = self.current_value[1] * self.inertia + 0.5 * (1 - self.inertia)
                d = self.current_value[2] * self.inertia + 0.5 * (1 - self.inertia)
                self.current_value = (
                    max(0.0, min(1.0, v)),
                    max(0.0, min(1.0, a)),
                    max(0.0, min(1.0, d))
                )
                logger.debug(
                    f"情感衰减后 VAD -> V:{self.current_value[0]:.2f}, "
                    f"A:{self.current_value[1]:.2f}, D:{self.current_value[2]:.2f}"
                )

    async def start(self):
        """启动情感衰减任务"""
        if not self.started:
            self.started = True
            self.task = asyncio.create_task(self.regressing_emotion())
            logger.info("情感衰减任务已启动")
        else:
            logger.warning("情感衰减任务已处于运行状态")

    async def stop(self):
        """停止情感衰减任务"""
        if self.started:
            self.started = False
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            logger.info("情感衰减任务已停止")
        else:
            logger.warning("情感衰减任务未在运行")

    async def get_current_vad(self):
        """获取当前VAD值"""
        async with self.lock:
            return self.current_value

    async def update_emotion(self,message:MessageEvent,chat_history:list):
        """
        根据对话事件更新情感状态
        """
        async with self.lock:
            past_value = self.current_value
            logger.debug(f"更新前情感状态 VAD -> V:{past_value[0]:.2f}, A:{past_value[1]:.2f}, D:{past_value[2]:.2f}")
        success = False
        cnt = global_config.llm_models['max_retrys']
        while not success and cnt > 0:
            # print(self.bot.llm_api.semantic_analysis(message, chat_history))
            # print(self.bot.llm_api.semantic_analysis(message, chat_history))
            try:
                emotion_weights = self.bot.llm_api.semantic_analysis(message, chat_history)["emotion"]
                success = True
            except Exception as e:
                logger.error(f"语义分析出错->{e}")
                cnt -= 1
        if not success or not isinstance(emotion_weights,dict):
            return
        logger.debug(f"收到情感权重更新: {emotion_weights}")
        
        
        # 计算情感影响
        v_sum, a_sum, d_sum = 0.0, 0.0, 0.0
        for emotion, weight in emotion_weights.items():
            vad = self.vad_lexicon.get(emotion, self.default_vad)
            v_sum += vad[0] * weight
            a_sum += vad[1] * weight
            d_sum += vad[2] * weight

        # 应用衰减因子并限制数值范围
        new_v = max(0.0, min(1.0, 
            v_sum * self.decay_factor + past_value[0] * (1 - self.decay_factor)))
        new_a = max(0.0, min(1.0, 
            a_sum * self.decay_factor + past_value[1] * (1 - self.decay_factor)))
        new_d = max(0.0, min(1.0, 
            d_sum * self.decay_factor + past_value[2] * (1 - self.decay_factor)))

        async with self.lock:
            self.current_value = (new_v, new_a, new_d)
            logger.info(
                f"情感更新完成 VAD -> V:{new_v:.2f}, A:{new_a:.2f}, D:{new_d:.2f} "
                f"(ΔV:{new_v - past_value[0]:+.2f}, ΔA:{new_a - past_value[1]:+.2f}, ΔD:{new_d - past_value[2]:+.2f})"
            )
    

    def handle_emotion(self,vad):
        valence, arousal, dominance = vad
        
        # Valence (愉悦度)
        if valence > 0.65:
            valence_prompt = random.choices(
                ["你的心情不错，可以用一些表示开心的词，也可以使用开心的颜文字！", "你非常开心！你一定会使用开心的词语，或附带开心的颜文字！"],
                [0.9, 0.1]  # 90% probability for the first, 10% for the second
            )[0]
        elif valence < 0.35:
            valence_prompt = random.choices(
                ["你的心情不太好，可以使用表示悲伤的词，或使用悲伤的颜文字", "你现在非常的沮丧与伤心，你一定会使用表示悲伤的词，或附带悲伤的颜文字。"],
                [0.8, 0.2]  # 80% for the first, 20% for the second
            )[0]
        else:
            valence_prompt = "你心情不好也不坏。"
        
        # Arousal (激烈度)
        if arousal > 0.65:
            arousal_prompt = random.choices(
                ["你现在心情偏激动，比较想说话。你的每句话说话长度不会短于5个字。", "你现在心情非常激动，特别想说话！你的每句话说话长度不会短于7个字！"],
                [0.85, 0.15]
            )[0]
        elif arousal < 0.35:
            arousal_prompt = random.choices(
                ["你心情较为冷静，不太想说较长的话。你的每句话长度不超过10个字。", "你心情极度冷静，不想说长话。你的每句话长度不超过8个字。"],
                [0.75, 0.25]
            )[0]
        else:
            arousal_prompt = "你心情不激动也不冷静，你可以正常说话。"
        
        # Dominance (支配感)
        if dominance > 0.65:
            dominance_prompt = random.choices(
                ["你看起来很有控制力，很自信。", "你极度自信。"],
                [0.8, 0.2]
            )[0]
        elif dominance < 0.35:
            dominance_prompt = random.choices(
                ["你可能会感到有点不知所措或被动。", "你处于一种极度脆弱的情绪状态。"],
                [0.7, 0.3]
            )[0]
        else:
            dominance_prompt = ""
        
        prompt = f"{valence_prompt} {arousal_prompt} {dominance_prompt}"
        return prompt