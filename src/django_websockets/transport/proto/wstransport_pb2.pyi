from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WSMessage(_message.Message):
    __slots__ = ["message", "params", "type"]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    message: str
    params: str
    type: str
    def __init__(self, type: _Optional[str] = ..., message: _Optional[str] = ..., params: _Optional[str] = ...) -> None: ...

class WSResponse(_message.Message):
    __slots__ = ["ack"]
    ACK_FIELD_NUMBER: _ClassVar[int]
    ack: bool
    def __init__(self, ack: bool = ...) -> None: ...

class WSSendMessageRequest(_message.Message):
    __slots__ = ["group", "message"]
    GROUP_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    group: str
    message: WSMessage
    def __init__(self, group: _Optional[str] = ..., message: _Optional[_Union[WSMessage, _Mapping]] = ...) -> None: ...
