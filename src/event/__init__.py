import json
import time

class MessageEvent:
    def __init__(self, self_id=None, user_id=None, message_id=None, sender=None, message=None, message_type=None, group_id=None, raw_message=None, time=None):
        self.self_id = self_id
        self.user_id = user_id
        self.message_id = message_id
        self.sender = sender
        self.message = message
        self.message_type = message_type
        self.group_id = group_id
        self.raw_message = raw_message
        self.time = time

    def __call__(self, messageEvent: str):
        messageEvent = json.loads(messageEvent)
        if messageEvent.get('post_type') != 'message':
            return None
        else:
            # 直接设置属性
            self.self_id = messageEvent.get('self_id')
            self.user_id = messageEvent.get('user_id')
            self.message_id = messageEvent.get('message_id')
            self.sender = Sender(messageEvent.get('sender'))
            self.message = Message(messageEvent.get('message'))
            self.message_type = messageEvent.get('message_type')
            self.group_id = messageEvent.get('group_id')
            self.raw_message = messageEvent.get('raw_message')
            self.time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(messageEvent.get('time')))
            return self

    def is_group(self):
        return self.message_type == 'group'
    
    def is_private(self):
        return self.message_type == 'private'

    def get_plaintext(self):
        for segment in self.message.segments:
            if segment.type == 'at' and segment.data.get('qq') != str(self.self_id):
                pass
        return "".join([segment.data.get('text') for segment in self.message.segments if segment.type == 'text'])

    def is_tome(self):
        for segment in self.message.segments:
            if segment.type == 'at' and (segment.data.get('qq') == 'all' or int(segment.data.get('qq')) == self.self_id):
                return True
        return False

    def get_id(self):
        return self.user_id if self.is_private() else self.group_id


class Segment:
    def __init__(self, type=None, data=None):
        self.type = type
        self.data = data


class Sender:
    def __init__(self, data=None):
        self.user_id = data.get('user_id')
        self.nickname = data.get('nickname')
        self.card = data.get('card')


class Message:
    def __init__(self, segments=None):
        self.segments = [Segment(**segment) for segment in segments] if segments else []