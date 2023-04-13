from typing import Any

from django.conf import settings
from django_websockets.middlewares.utils import get_cookie
from django_websockets.middlewares import Middleware
from websockets.server import WebSocketServerProtocol
from django.contrib.sessions.middleware import SessionMiddleware

from django_websockets.middlewares.utils import database_sync_to_async


class Scope(dict):
    
    def __getattr__(self, __name: str):
        try:
            return super().__getattr__(__name)
        except:
            return self[__name]
    
    def __setattr__(self, __name: str, __value: Any) -> None:
        self[__name] = __value


class ScopeMiddleware(Middleware):
    """
    Creates the session scope
    """

    async def __call__(self, websocket: WebSocketServerProtocol, call_next_middleware):

        scope = Scope()

        scope['HEADERS'] = websocket.request_headers
        scope['COOKIES'] = get_cookie(websocket)

        sm = SessionMiddleware()
        await database_sync_to_async(sm.process_request)(scope)

        session_key = scope['COOKIES'].get(settings.SESSION_COOKIE_NAME)
        scope['session'] = sm.SessionStore(session_key)

        websocket.scope = scope

        return await call_next_middleware()
