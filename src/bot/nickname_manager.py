from .logger import register_logger
from ..event import MessageEvent, Sender

from .config import global_config

logger = register_logger("nickname manager",global_config.log_level)

class NicknameManager:
    def __init__(self):
        '''
        维护在群聊/私聊中频繁出现的 ID 对应的昵称，并在 @ 的时候生成对应的 prompt
        '''
        self.id_nickname = {}
        logger.info("识别昵称系统启动")
    
    def update_after_recv(self, messageEvent:MessageEvent) -> None:
        self.known_after_recv(messageEvent)
        if messageEvent.at_list!=[]:
            tmp = ["全体成员"] if messageEvent.at_list[0]=="all" else []
            for i in messageEvent.at_list:
                if i in self.id_nickname.keys():
                    tmp.append(self.id_nickname[i].nickname)
            if tmp==[]:
                tmp = ["其他人"]
            messageEvent.at_list = tmp
        self.regress_after_recv()

    def known_after_recv(self, messageEvent:MessageEvent) -> None:
        key = str(messageEvent.sender.user_id)
        if str(messageEvent.self_id) not in self.id_nickname:
            self.id_nickname[str(messageEvent.self_id)] = Nickname(global_config.bot_config["nickname"])
        if key not in self.id_nickname:
            self.id_nickname[key] = Nickname(messageEvent.sender.nickname)
            logger.debug(f'认识了 {self.id_nickname[key].nickname}[ID: {messageEvent.sender.user_id}]')
        else:
            self.id_nickname[key].weight += 1
    
    def regress_after_recv(self) -> None:
        tmp_key = list(self.id_nickname.keys())
        for i in tmp_key:
            self.id_nickname[i].weight -= 0.05
            if self.id_nickname[i].weight < 0 and self.id_nickname[i].nickname!=global_config.bot_config["nickname"]:
                logger.debug(f'遗忘 {self.id_nickname[i].nickname}[ID: {i}]')
                self.id_nickname.pop(i)
    
class Nickname:
    def __init__(self, nickname):
        self.nickname = nickname
        self.weight = 1