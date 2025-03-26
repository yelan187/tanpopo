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

    def update_discriptions(self,discriptions):
        if discriptions == []:
            return
        self.message.update_discriptions(discriptions)

    def update_reply(self,reply):
        if reply is None:
            return
        self.message.update_reply(reply)

    def get_plaintext(self,with_at:bool=True):
        prefix = ""
        if self.at_list!=[]:
            for i in self.at_list:
                prefix += f"@{i} "
        
        plaintext = ""
        for segment in self.message.segments:
            if segment.type == 'text':
                plaintext += segment.data.get('text')
            elif segment.type == 'at':
                plaintext += prefix if with_at else ""
            elif segment.type == 'image':
                plaintext += "[图片]"
                d = segment.data.get('discription')
                plaintext += d if d is not None else ""
            elif segment.type == "reply":
                plaintext += "[引用]"
                d = segment.data.get("plaintext")
                plaintext += d if d is not None else ""
            plaintext += " "

        return plaintext
    
    def get_text(self):
        text = ""
        for segment in self.message.segments:
            if segment.type == 'text':
                text += segment.data.get('text')
        return text
    
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

    def get_imgs_url(self):
        """获取图片url及是否是表情包"""
        urls = []
        is_meme = []
        for seg in self.message.segments:
            if seg.type == "image":
                urls.append(seg.data.get("url"))
                try:
                    if int(seg.data.get("sub_type")) == 1:
                        is_meme.append(True)
                    else:
                        is_meme.append(False)
                except:
                    is_meme.append(False)

        return  (urls,is_meme)

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

    def update_discriptions(self, discriptions:list[str]):
        cnt = 0
        for segment in self.segments:
            if segment.type == 'image':
                segment.data['discription'] = discriptions[cnt]
                cnt += 1

    def update_reply(self,reply:MessageEvent):
        for Segment in self.segments:
            if Segment.type == "reply":
                Segment.data['plaintext'] = reply.get_text()