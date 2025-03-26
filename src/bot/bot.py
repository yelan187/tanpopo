import json
import random
import requests
import asyncio

from ..event import MessageEvent
from .prompt_builder import PromptBuilder
from .message_buffer import MessageManager
from .llmapi import LLMAPI
from .config import global_config
from .memory import Memory, MemoryPiece
from .schedule_generator import ScheduleGenerator
from .nickname_manager import NicknameManager
from .willing_manager import WillingManager
from .logger import register_logger
from .image_manager import ImageManager
from .action_controller import ActionController
from .emotion_manager import EmotionManager
from ..ws import WS

logger = register_logger("bot", global_config.log_level)


class Bot:
    def __init__(self, ws: WS):
        self.prompt_builder = PromptBuilder(global_config.enabled_prompts)
        self.llm_api = LLMAPI(global_config.llm_auth, global_config.llm_models)
        self.message_manager = MessageManager()
        # self.schedule_generator = ScheduleGenerator()
        self.willing_manager = WillingManager()
        self.nickname_manager = NicknameManager()
        self.image_manager = ImageManager()
        self.memory = Memory(self)
        self.action_controller = ActionController(self)
        # self.emotion_manager = EmotionManager(self)

        # asyncio.create_task(self.emotion_manager.start())
        # 启动定时任务
        asyncio.create_task(self.message_manager.start_task())
        asyncio.create_task(self.image_manager.load_memes())
        asyncio.create_task(self.willing_manager.start_regression_task())
        asyncio.create_task(self.memory.start_building_task())
        asyncio.create_task(self.memory.start_forgetting_task())

        self.ws = ws

    async def handle_message(self, messageEvent: MessageEvent):
        """
        消息处理函数

        :param messageEvent: 处理的消息事件
        """
        logger.info(
            f"收到来自{'群聊'+str(messageEvent.group_id) if messageEvent.is_group() else '私聊'}的消息->({messageEvent.message_id}){messageEvent.raw_message}"
        )
        if messageEvent.is_group():
            self.nickname_manager.update_after_recv(messageEvent)
            desriptions = await self.image_manager.create_img_description_update(
                *messageEvent.get_imgs_url()
            )#获取图片描述
            messageEvent.update_discriptions(desriptions)#将图片描述更新到message中
            messageEvent.update_reply(await self.get_reply(messageEvent))#获取消息中的回复并更新
            await self.message_manager.push_message(
                messageEvent.get_id(), messageEvent.is_private(), messageEvent
            )#将消息存入历史消息队列
            chat_history = await self.message_manager.get_all_messages(
                messageEvent.get_id(), messageEvent.is_private()
            )#获取历史消息
            willing = await self.willing_manager.change_willing_after_receive(
                messageEvent
            )#收到消息时更新回复意愿
            # await self.emotion_manager.update_emotion(messageEvent,chat_history)
            if (
                messageEvent.group_id in global_config.group_talk_allowed
                and random.random() < willing
            ):
                await self.willing_manager.change_willing_if_thinking(
                    messageEvent.group_id
                )#思考时更新回复意愿
                # routine = self.schedule_generator.get_current_task()
                relavant_memories = await self.memory.recall(messageEvent)#获取关联记忆

                user_prompt = self.prompt_builder.build_user_prompt(
                    current_message=messageEvent,
                    chat_history=chat_history,
                    relavant_memories=relavant_memories,
                    # routine=routine,
                    img_descriptions=desriptions,
                )#构建prompt
                sys_prompt = self.prompt_builder.build_sys_prompt()
                logger.debug(f"构建prompt->{user_prompt}")
                success = False
                cnt = global_config.llm_models["max_retrys"]
                while not success and cnt > 0:
                    logger.info(f"bot选择回复")
                    try:
                        json_resp = self.llm_api.send_request_text_full(
                            sys_prompt, user_prompt
                        )
                        success = True
                    except Exception as e:
                        cnt -= 1
                        logger.error(f"请求失败,重新请求->{e}")
                if not success:
                    return
                logger.warning(f"原始响应->{json_resp}")
                resp = json_resp.get("reply", None)
                if resp == None:
                    logger.warning("回复无法解析")
                    return
                actions = json_resp.get("actions", [])
                actions.append("回复")
                await self.action_controller.handle(
                    actions, resp=resp, message=messageEvent
                )#处理动作（包括回复）
            else:
                logger.info(f"bot选择不回复")
                return

    async def get_reply(self, message: MessageEvent) -> MessageEvent:
        """
        获取消息中的引用消息

        :param message: 消息事件
        :return: 引用消息
        """
        for seg in message.message.segments:
            if seg.type == "reply":
                url = f"http://{global_config.http_settings['host']}:3000/"
                data = {"message_id": f"{seg.data['id']}"}
                resp = requests.post(url + "get_msg", data=data)
                msg = MessageEvent(resp.json()["data"])
                msg.update_discriptions(
                    await self.image_manager.create_img_description_update(
                        *msg.get_imgs_url()
                    )
                )
                return msg
        return None
