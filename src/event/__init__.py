import json
from ..bot.config import global_config

def build(obj, json):
    for key,value in json.items():
        value = value if value != "" else None
        if key in obj.rules:
            if key == 'message':
                messageobj = Message(value)
                setattr(obj, key, messageobj)
            elif isinstance(value, dict):
                sub_obj = locals()[key[0].upper() + key[1:]]()
                build(sub_obj, value)
                setattr(obj, key, sub_obj)
            else:
                setattr(obj, key, value)

class MessageEvent:
    def __init__(self,rules = None):
        if rules == None:
            self.rules = [
                "self_id",
                "user_id",
                "message_id",
                "sender",
                "message",
                "message_type",
                "group_id"
            ]
        else:
            self.rules = rules

    def __call__(self, messageEvent: str):
        messageEvent = json.loads(messageEvent)
        if messageEvent.get('post_type') != 'message':
            return None
        else:
            build(self,messageEvent)
            return self

    def is_group(self):
        return self.message_type == 'group'
    
    def is_tome(self):
        for segment in self.message.segments:
            if segment.type == 'at' and segment.data.get('qq') == 'all' or segment.data.get('qq') == self.self_id:
                return True
        return False

class Segment:
    def __init__(self,segment):
        self.type = segment.get('type')
        self.data = segment.get('data')

class Sender:
    def __init__(self,rules = None):
        if rules == None:
            self.rules = [
                "user_id",
                "nickname",
                "card"
            ]
        else:
            self.rules = rules

class Message:
    def __init__(self,segments):
        self.segments = [Segment(segment) for segment in segments]

    
