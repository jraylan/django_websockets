from typing import Union, Optional


class GroupMessage(object):
    slots = ('type', 'message', 'params')

    def __init__(self, type: str, message: Union[str, bytes], params:Optional[Union[str, bytes]]=None):
        self.type = type
        self.message = message
        self.params = params

    def keys(self):
        return self.slots
    
    def values(self):
        return [
            self.type,
            self.message,
            self.params
        ]
    
    def __getitem__(self, item):
        return self.__getattribute__(item)
