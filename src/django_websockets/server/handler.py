from websockets.server import WebSocketServerProtocol

from django_websockets.middlewares import call_middleware_stack
from django_websockets.consumers import StopConsumer


async def connection_handler(websocket: WebSocketServerProtocol, path=""):
    try:
        await call_middleware_stack(websocket)
    except StopConsumer:
        await websocket.close(1000)
