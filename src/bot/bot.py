import json
import logging

from ..event import MessageEvent
from .prompt_builder import promptBuilder
from .message_buffer import MessageManager
from .llmapi import llmApi
from .config import global_config
from .memory import Memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] | %(message)s",
    handlers=[logging.StreamHandler()],
)

class Bot:
    def __init__(self,ws):
        self.prompt_builder =promptBuilder(global_config.enabled_prompts)
        self.llm_api = llmApi(global_config.gpt_settings)
        self.message_manager = MessageManager()
        self.ws = ws
        self.memory = Memory()

    def handle_message(self, messageEvent:MessageEvent) -> list[str]:
        """
        消息处理函数
        Args:
            message (MessageEvent): 消息事件
        """
        if messageEvent.is_group():
            self.message_manager.push_message(messageEvent.group_id,False,messageEvent)
            if messageEvent.is_tome():
                # print("收到群聊消息")
                relavant_memories = self.memory.recall(messageEvent)
                chat_history = self.message_manager.get_all_messages(messageEvent.group_id,False)
                prompt = self.prompt_builder.build_prompt(messageEvent,chat_history,relavant_memories)
                logging.info(f"思考prompt:{prompt}")
                raw_resp = self.llm_api.send_request_text(prompt) 
                resp = raw_resp.split("。")
                return [self.wrap_message(messageEvent.message_type,messageEvent.group_id,part) for part in resp if part]
            else:
                return []

    def wrap_message(self, message_type, id, message: str) -> str:
        tmp = {
                'action': 'send_msg',
                'params': {
                    'message_type': message_type,
                    'message': '114514::' + message
                }
            }
        if message_type == 'private':
            tmp['params']['user_id'] = id
        else:
            tmp['params']['group_id'] = id
        
        return json.dumps(tmp)