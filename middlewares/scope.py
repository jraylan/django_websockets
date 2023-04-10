from typing import Any
from utils import get_cookie
from . import Middleware
from websockets.server import WebSocketServerProtocol
from asgiref.sync import sync_to_async
from django.contrib.sessions.middleware import SessionMiddleware


class Scope(dict):
    
    def __getattr__(self, __name: str):
        try:
            return super().__getattr__(__name)
        except:
            return self[__name]
    
    def __setattr__(self, __name: str, __value: Any) -> None:
        self[__name] = __value


class ScopeMiddleware(Middleware):

    async def __call__(self, websocket: WebSocketServerProtocol, call_next_middleware):
        cookies = get_cookie(websocket)
        if not cookies.get('sessionid'):
            print('not authorized')

        scope = Scope()

        scope['HEADERS'] = websocket.request_headers
        scope['COOKIES'] = cookies

        sm = SessionMiddleware()
        await sync_to_async(sm.process_request)(scope)

        websocket.scope = scope


        return await call_next_middleware()
