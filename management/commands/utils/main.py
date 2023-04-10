import asyncio
import websockets
import management.commands.utils.arguments as arguments
from handler import connection_handler


async def main(bind: arguments.WebsocketBindAddress):
    if bind.is_unix:
        server = websockets.unix_serve(connection_handler, path=bind.address)
    else:
        server = websockets.serve(connection_handler, bind.address, bind.port)

    async with server:
        await asyncio.Future()  # run forever