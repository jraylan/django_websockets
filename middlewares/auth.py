from . import Middleware
from websockets.server import WebSocketServerProtocol
from django.contrib.auth import get_user
from asgiref.sync import sync_to_async


class AuthMiddleware(Middleware):

    async def __call__(self, websocket: WebSocketServerProtocol, call_next_middleware):
        if not hasattr(websocket, 'scope'):
            return
        
        if not websocket.scope.get('session'):
            raise RuntimeError("This middleware requires ScopeMiddleware")
        
        websocket.scope['user'] = await sync_to_async(get_user)(websocket.scope)

        return await call_next_middleware()
