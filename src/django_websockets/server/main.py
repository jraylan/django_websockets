import asyncio
from functools import partial
import websockets
import django_websockets.server.arguments as arguments
from django.utils.module_loading import import_string
from django_websockets.transport import get_channel_layer, channel_layers
from handler import connection_handler


async def main(bind: arguments.WebsocketBindAddress):
    from django.conf import settings

    if bind.is_unix:
        server = websockets.unix_serve(
            connection_handler, path=bind.address)
    else:
        server = websockets.serve(
            connection_handler, bind.address, bind.port)

    async with server:
        await asyncio.gather(*[
            get_channel_layer(using=layer)()
            for layer in channel_layers
        ])
