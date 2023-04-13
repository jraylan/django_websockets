import asyncio
from django_websockets.middlewares import Middleware
from websockets.server import WebSocketServerProtocol
from django.conf import settings
import importlib
from django_websockets.middlewares.utils import database_sync_to_async


class RouteMiddleware(Middleware):

    async def __call__(self, websocket: WebSocketServerProtocol, call_next_middleware):
        module = importlib.import_module(settings.WEBSOCKET_ROUTE_MODULE)

        found = False
        for pattern in module.urlpatterns:
            resolver_match = pattern.resolve(websocket.path)
            if resolver_match:
                found = True
                websocket.scope['url_route'] = {
                    'url': websocket.path,
                    'args': resolver_match.args,
                    'kwargs': resolver_match.kwargs
                }
                if asyncio.iscoroutinefunction(resolver_match.func):
                    await resolver_match.func(
                        websocket,
                        *resolver_match.args,
                        **resolver_match.kwargs
                    )
                else:
                    await database_sync_to_async(
                        resolver_match.func
                    )(
                        websocket,
                        *resolver_match.args,
                        **resolver_match.kwargs
                    )
        if not found:
            print(websocket.path)
            for p in module.urlpatterns:
                print(p)
            return await websocket.close(1003, "not_found")

        return await call_next_middleware()
