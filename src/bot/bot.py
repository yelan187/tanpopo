import json
import time
import random

from ..event import MessageEvent
from .prompt_builder import promptBuilder
from .message_buffer import MessageManager
from .llmapi import llmApi
from .config import global_config
from .memory import Memory
from .schedule_generator import scheduleGenerator
from .logger import register_logger
from ..ws import WS

logger = register_logger("bot",global_config.log_level)

class Bot:
    def __init__(self,ws:WS):
        self.prompt_builder =promptBuilder(global_config.enabled_prompts)
        self.llm_api = llmApi(global_config.gpt_settings)
        self.message_manager = MessageManager()
        self.schedule_generator = scheduleGenerator()
        self.memory = Memory()
        self.ws = ws

    async def handle_message(self, messageEvent:MessageEvent) -> list[str]:
        """
        消息处理函数
        Args:
            message (MessageEvent): 消息事件
        """
        # key_words = self.llm_api.get_keywords(messageEvent)
        # emotion = self.llm_api.get_emotion(messageEvent)
        # relavant_memories = self.memory.recall(messageEvent,key_words)
        if messageEvent.is_group():
            logger.info(f"收到来自群{messageEvent.group_id}的消息->{messageEvent.get_plaintext()}")
            self.message_manager.push_message(messageEvent.group_id,False,messageEvent)
            if (messageEvent.group_id in global_config.group_talk_allowed and random.random() < 0.3) or messageEvent.is_tome():
                # relavant_memories = self.memory.recall(messageEvent)
                relavant_memories = None
                chat_history = self.message_manager.get_all_messages(messageEvent.group_id,False)
                routine = self.schedule_generator.get_current_task()
                prompt = self.prompt_builder.build_prompt(
                    current_message = messageEvent,
                    chat_history = chat_history,
                    relavant_memories = relavant_memories,
                    routine = routine,
                )
                logger.debug(f"构建prompt->{prompt}")
                raw_resp = self.llm_api.send_request_text(prompt) 
                resp = raw_resp.split("。")
                for part in resp:
                    if part=="":
                        continue
                    logger.info(f"bot回复->{part}")
                    time.sleep(len(part)//2)
                    await self.ws.send(self.wrap_message(messageEvent.message_type,messageEvent.group_id,part))
            else:
                return []
            
    def wrap_message(self, message_type, id, message: str) -> str:
        tmp = {
                'action': 'send_msg',
                'params': {
                    'message_type': message_type,
                    'message': message
                }
            }
        if message_type == 'private':
            tmp['params']['user_id'] = id
        else:
            tmp['params']['group_id'] = id

        return json.dumps(tmp)
    
    def get_nickname_by_id(self, group_id, user_id, no_cache=False) -> str:
        tmp = {
                'action': 'get_group_member_info',
                'params': {
                    'group_id': group_id,
                    'user_id': user_id,
                    'no_cache': no_cache
                }
            }
        self.ws.send(json.dumps(tmp))
        res = self.ws.recv()
        print(res)