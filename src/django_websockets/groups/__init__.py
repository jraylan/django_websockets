from typing import Union


class GroupMessage(object):
    slots = ('type', 'message')

    def __init__(self, type: str, message: Union[str, bytes]):
        self.type = type
        self.message = message
