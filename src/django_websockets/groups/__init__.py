from typing import Union


class GroupMessage(object):
    slots = ('type', 'message')

    def __init__(self, type: str, message: Union[str, bytes]):
        self.type = type
        self.message = message

    def keys(self):
        return self.slots
    
    def values(self):
        return [
            self.type,
            self.message
        ]
    
    def __getitem__(self, item):
        return self.__getattribute__(item)
