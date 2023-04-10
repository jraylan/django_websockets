from websockets.server import WebSocketServerProtocol

from middlewares import call_middleware_stack


async def connection_handler(websocket: WebSocketServerProtocol, path=""):
    await call_middleware_stack(websocket)
