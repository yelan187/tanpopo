import time

class MessageEvent:
    def __init__(self, messageEvent:dict):
        self.self_id = messageEvent.get('self_id')
        self.user_id = messageEvent.get('user_id')
        self.message_id = messageEvent.get('message_id')
        self.sender = Sender(messageEvent.get('sender'))
        self.message = Message(messageEvent.get('message'))
        self.message_type = messageEvent.get('message_type')
        self.group_id = messageEvent.get('group_id')
        self.raw_message = messageEvent.get('raw_message')
        self.time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(messageEvent.get('time')))
        self.at_list = self.get_at_list()
        self.is_tome = str(self.self_id) in self.at_list or self.at_list==["all"]

    def is_group(self):
        return self.message_type == 'group'

    def is_private(self):
        return self.message_type == 'private'

    def get_plaintext(self):
        prefix = ""
        if self.at_list!=[]:
            for i in self.at_list:
                prefix += f"@{i} "
        return prefix+"".join([segment.data.get('text') for segment in self.message.segments if segment.type == 'text'])

    def get_at_list(self):
        tmp = []
        for segment in self.message.segments:
            if segment.type == "at":
                if segment.data.get("qq") == "all":
                    tmp = ["all"]
                    break
                else:
                    tmp.append(segment.data.get("qq"))
        return tmp

    def get_memes_url(self) -> list[str]:
        """获取表情包url"""
        result = []
        for seg in self.message.segments:
            if seg.type == "image" and int(seg.data.get("sub_type")) == 1:
                result.append(seg.data.get("url"))
        return result

    def get_images_url(self) -> list[str]:
        """获取图片url"""
        result = []
        for seg in self.message.segments:
            if seg.type == "image" and int(seg.data.get("sub_type")) == 0:
                result.append(seg.data.get("url"))
        return result

    def is_tome(self):
        for segment in self.message.segments:
            if segment.type == 'at':
                if segment.data.get('qq')=="all":
                    tmp = ["all"]
                    break
                else:
                    tmp.append(segment.data.get('qq'))
        return tmp

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
