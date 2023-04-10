from functools import partial
import importlib
from typing import Awaitable, Callable
from websockets.server import WebSocketServerProtocol

class MiddlewareLoaderIterator:

    def __init__(self, loader):
        self.__loader = loader
        self.__idx = 0

    def __next__(self):
        try:
            return self.__loader[self.__idx]
        except IndexError:
            raise StopIteration()
        finally:
            self.__idx += 1

    def next(self):
        return self.__next__()

class MiddlewareLoader:

    def __len__(self):
        from django.conf import settings
        return len(getattr(settings, 'WEBSOCKET_MIDDLEWARE', tuple()))

    def __getitem__(self, index):
        from django.conf import settings
        module_path = getattr(settings, 'WEBSOCKET_MIDDLEWARE')[index].split('.')
        return getattr(importlib.import_module('.'.join(module_path[:-1])), module_path[-1])
    
    def __iter__(self):
        return MiddlewareLoaderIterator(self)


active_middlewares = MiddlewareLoader()


class Middleware(object):

    async def __call__(self, websocket: WebSocketServerProtocol, call_next_middleware: Awaitable[Callable[[], "Middleware"]]):
        raise NotImplementedError("")


async def call_middleware_stack(websocket: WebSocketServerProtocol, idx=0):
    if len(active_middlewares) > idx:
        return await active_middlewares[idx]()(websocket, partial(call_middleware_stack, websocket, idx+1))
