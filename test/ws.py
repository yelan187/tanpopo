class message:
    def __init__(self,data):
        self.data = 4
    def __call__(self,data):
        if data == 1:
            return None
        elif data == 2:
            return self.__init__(1)
        else:
            return self
        
callback = message

print(callback(1)(1))