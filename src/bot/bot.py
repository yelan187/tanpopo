import json
import random
import asyncio

import jieba
import jieba.analyse

from .database import Database
from ..event import MessageEvent
from .prompt_builder import PromptBuilder
from .message_buffer import MessageManager
from .llmapi import LLMAPI
from .config import global_config
from .memory import Memory,MemoryPiece
from .schedule_generator import ScheduleGenerator
from .nickname_manager import NicknameManager
from .willing_manager import WillingManager
from .logger import register_logger
from .image_manager import ImageManager
from ..ws import WS

logger = register_logger("bot", global_config.log_level)


class Bot:
    def __init__(self, ws: WS):
        self.prompt_builder = PromptBuilder(global_config.enabled_prompts)
        self.llm_api = LLMAPI(global_config.gpt_settings)
        self.message_manager = MessageManager()
        self.schedule_generator = ScheduleGenerator()
        self.willing_manager = WillingManager()
        self.nickname_manager = NicknameManager()
        self.image_manager = ImageManager()
        self.memory = Memory(self)

        asyncio.create_task(self.message_manager.start_task())
        asyncio.create_task(self.image_manager.load_memes())
        asyncio.create_task(self.willing_manager.start_regression_task())
        asyncio.create_task(self.memory.start_building_task())

        self.ws = ws

    async def handle_message(self, messageEvent: MessageEvent):
        """
        消息处理函数
        Args:
            message (MessageEvent): 消息事件
        """
        logger.info(
            f"收到来自{'群聊'+str(messageEvent.group_id) if messageEvent.is_group() else '私聊'}的消息->{messageEvent.raw_message}"
        )
        await self.message_manager.push_message(
            messageEvent.get_id(), messageEvent.is_private(), messageEvent
        )
        chat_history = await self.message_manager.get_all_messages(
            messageEvent.get_id(), messageEvent.is_private()
        )
        if messageEvent.is_group():
            self.nickname_manager.update_after_recv(messageEvent)
            desriptions = await self.image_manager.create_img_description_update(*messageEvent.get_imgs_url())
            willing = await self.willing_manager.change_willing_after_receive(
                messageEvent
            )  # 收到消息时更新回复意愿
            if (messageEvent.group_id in global_config.group_talk_allowed and random.random() < willing):
                await self.willing_manager.change_willing_if_thinking(
                    messageEvent.group_id
                )
                routine = self.schedule_generator.get_current_task()
                analysis_result = self.llm_api.semantic_analysis(messageEvent,chat_history)
                relavant_memories = self.memory.recall(analysis_result.get("keywords"),analysis_result.get("summary"))
                logger.debug(f"当前上下文摘要->{analysis_result.get('summary')}")
                
                user_prompt = self.prompt_builder.build_user_prompt(
                    current_message=messageEvent,
                    chat_history=chat_history,
                    relavant_memories=relavant_memories,
                    routine=routine,
                    img_descriptions=desriptions
                )
                sys_prompt = self.prompt_builder.build_sys_prompt()
                logger.debug(f"构建prompt->{user_prompt}")
                json_resp = self.llm_api.send_request_text_full(sys_prompt,user_prompt)
                logger.warning(f"原始响应->{json_resp}")
                resp = json_resp.get("reply",None)
                if resp is None:
                    logger.warning("回复无法解析")
                    return
                for part in resp:
                    if part == "":
                        continue
                    logger.info(f"bot回复->{part}")
                    # await self.ws.send(self.wrap_message(messageEvent.message_type,messageEvent.group_id,part))
                    await self.push_bot_msg(messageEvent,part)
                    await asyncio.sleep(len(part) // 2)
                # meme = await self.image_manager.match_meme(raw_resp)
                # if random.random() < 1:
                #     await self.ws.send(self.wrap_image(messageEvent.message_type,messageEvent.group_id,meme))
            else:
                logger.info(f"bot选择不回复")
                return

    def wrap_image(self,message_type,id,image_base64)->str:
        tmp = {
            "action": "send_msg",
            "params": {
                "message_type": message_type,
                "message": [
                    {
                        "type": "image",
                        "data":{
                            "file": "base64://"+image_base64,
                            "sub_type":1
                        }
                    }
                ]
            },
        }
        if message_type == "private":
            tmp["params"]["user_id"] = id
        else:
            tmp["params"]["group_id"] = id
        return json.dumps(tmp)

    def wrap_message(self, message_type, id, message: str) -> str:
        tmp = {
            "action": "send_msg",
            "params": {"message_type": message_type, "message": message},
        }
        if message_type == "private":
            tmp["params"]["user_id"] = id
        else:
            tmp["params"]["group_id"] = id

        return json.dumps(tmp)

    def get_keywords(self,chat_history:list[MessageEvent]):
        plaintext = ""
        for message in chat_history:
            # plaintext += f"[{message.sender.nickname}]:{message.get_plaintext()}\n"
            plaintext += f"{message.get_plaintext()}\n"

        # logger.info(f"当前上下文->{plaintext}")
        keywords = jieba.analyse.extract_tags(plaintext, topK=5)
        return keywords
    
    async def push_bot_msg(self, messageEvent:MessageEvent, part:str) -> None:
        sent_msg = {
            "self_id":messageEvent.self_id,
            "user_id":messageEvent.self_id,
            "group_id":messageEvent.group_id,
            "sender":{
                "user_id":messageEvent.self_id,
                "nickname":"我"
            },
            "message":[
                {
                    "type":"text",
                    "data":{
                        "text":part
                    }
                }
            ]
        }
        sent_message = MessageEvent(sent_msg)
        await self.message_manager.push_message(messageEvent.group_id,False,sent_message)
