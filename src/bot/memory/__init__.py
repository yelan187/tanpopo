class Memory():
    def __init__(self):
        pass

    def recall(self,keywords:list[str]) -> dict[str,list[str]]:
        """
        根据关键词更新并返回相关记忆
        """
        if keywords == []:
            return {}