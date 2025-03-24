import asyncio
import json
import random
from datetime import datetime

from .config import global_config
from .logger import register_logger
from ..event import MessageEvent

logger = register_logger("action controller")

class ActionController:
    def __init__(self, bot):
        from .bot import Bot
        self.bot:Bot = bot
        self.mapping = {
            "回复":["reply",5],
            "艾特发送者":["at",0],
            "发送表情包":["send_meme",10],
        }

    async def handle(self, actions,**args):
        action_sorted = sorted(actions,key=lambda x:self.mapping.get(x,[0,0])[1])
        for action in action_sorted:
            if action not in self.mapping:
                logger.warning(f"未知动作{action}")
            await getattr(self,"_"+self.mapping[action][0],None)(**args)

    async def send_text(self,part:str,message:MessageEvent,is_first:bool):
        msg = []
        if is_first and (random.random() < 0.5 or datetime.now(global_config.time_zone).timestamp() - datetime.strptime(message.time, "%Y-%m-%d %H:%M:%S").timestamp() > 20 ):
            reply_id = message.message_id
            msg.append({"type": "reply", "data": {"id": reply_id}})

        at_id = getattr(self,"at_id",None)
        if at_id is not None:
            msg.append({"type": "at", "data": {"qq": at_id}})
            part = " " + part
            self.at_id = None
        msg.append({"type": "text", "data": {"text": part}})
        tmp = {
            "action": "send_msg",
            "params": {"message_type": message.message_type, "message": msg}
        }
        if message.message_type == "private":
            tmp["params"]["user_id"] = message.user_id
        else:
            tmp["params"]["group_id"] = message.group_id
        logger.info(f"bot回复->{part}")
        await self.bot.ws.send(json.dumps(tmp))
        await self.push_bot_msg(msg,message)

    async def push_bot_msg(self,msg:list, messageEvent: MessageEvent) -> None:
        sent_msg = {
            "self_id": messageEvent.self_id,
            "user_id": messageEvent.self_id,
            "group_id": messageEvent.group_id,
            "sender": {
                "user_id": messageEvent.self_id,
                "nickname": global_config.bot_config["nickname"],
            },
            "message": msg
        }
        sent_message = MessageEvent(sent_msg)
        await self.bot.message_manager.push_message(
            messageEvent.group_id, False, sent_message
        )

    async def send_image(self,base64_img:str,message:MessageEvent):
        tmp = {
            "action": "send_msg",
            "params": {
                "message_type": message.message_type,
                "message": [
                    {
                        "type": "image",
                        "data":{
                            "file": "base64://"+base64_img,
                            "sub_type":1
                        }
                    }
                ]
            },
        }
        if message.message_type == "private":
            tmp["params"]["user_id"] = message.user_id
        else:
            tmp["params"]["group_id"] = message.group_id
        logger.info("bot发送了表情包")
        await self.bot.ws.send(json.dumps(tmp))

    async def _at(self,message:MessageEvent,**args):
        self.at_id = message.sender.user_id
        logger.info("bot决定@发送者")

    async def _reply(self,message:MessageEvent,resp,**args):
        is_first = True
        for part in resp:
            if not is_first:
                await asyncio.sleep(len(part)//3)
            await self.send_text(part,message,is_first=is_first)
            is_first = False

    async def _send_meme(self,message:MessageEvent,resp,**args):
        meme = await self.bot.image_manager.match_meme("。".join(resp))
        if meme:
            await self.send_image(meme,message)
