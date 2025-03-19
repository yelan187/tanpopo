import json

class Message:
    def __init__(self,rules = None):
        if rules == None:
            self.rules = []
        else:
            self.rules = rules

    def __call__(self, message: str):
        message = json.loads(message)
        if message.get('post_type') != 'message':
            return None
        else:
            self.build(message)
            return self

    def build(self, message):
        for field in self.rules:
            # 分割字段，以支持嵌套的字段访问，如 sender.nickname
            keys = field.split('.')
            value = message
            for key in keys:
                value = value.get(key, None)
                if value is None:
                    break
            setattr(self, field, value)