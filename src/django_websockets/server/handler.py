import asyncio
from functools import partial
import traceback
import websockets
import re
from websockets.server import WebSocketServerProtocol
from websockets.client import WebSocketClientProtocol

from django_websockets.middlewares import call_middleware_stack
from django_websockets.consumers import StopConsumer
from django_websockets.server.arguments import WebsocketBindAddress
from django_websockets.server.horchestration import RoundRobQueue

from websockets.datastructures import Headers


async def connection_handler(websocket: WebSocketServerProtocol, path=""):
    try:
        await call_middleware_stack(websocket)
    except StopConsumer:
        await websocket.close(1000)


async def _recv_from_client(server_socket: WebSocketClientProtocol, client_socket: WebSocketServerProtocol):
    while True:
        message = await client_socket.recv()
        await server_socket.send(message)

async def _recv_from_worker(server_socket: WebSocketClientProtocol, client_socket: WebSocketServerProtocol):
    while True:
        message = await server_socket.recv()
        await client_socket.send(message)


async def handle_connection(bind, worker_queue, extra_headers, path, client_socket):
    try:
        if bind.is_unix:
            # Get next worker websocket address
            address = bind.get_namespaced_address(worker_queue.next())
            connection = websockets.unix_connect(
                address,
                uri=f'ws://localhost:8080{path}',
                extra_headers=extra_headers)
        else:
            worker_index = int(re.sub(r'[^0-9]', '', worker_queue.next())) + 1
            address = f'ws://{bind.address}:{bind.port + worker_index}{path}'
            connection = websockets.connect(
                address, extra_headers=extra_headers)
            
        async with connection as server_socket:
            await asyncio.gather(
                _recv_from_client(server_socket, client_socket),
                _recv_from_worker(server_socket, client_socket),
            )
    except ConnectionRefusedError:
        await asyncio.sleep(0.1)
        raise StopConsumer
    else:
        return connection

async def _master_handler(bind: WebsocketBindAddress, worker_queue: RoundRobQueue, client_socket: WebSocketServerProtocol, path=""):
    try:
        if not path:
            path = client_socket.path

        # Forward Headers
        extra_headers = Headers()

        for header in ['Cookie', 'User-Agent', 'Origin', 'Accept-Encoding', 'Accept-Language']:
            extra_headers[header] = client_socket.request_headers.get(header)
            

        for header in client_socket.request_headers:
            if header.startswith('x-') or header.startswith('X-'):
                extra_headers[header] = client_socket.request_headers.get(header)

        extra_headers['Host'] = re.sub(r'^(http|ws)s?\:\/\/', '', extra_headers['Origin'])

        await handle_connection(
            bind, worker_queue, extra_headers, path, client_socket)


    except (StopConsumer):
        await client_socket.close(1000)
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except:
        traceback.print_exc()

def master_handler(bind: WebsocketBindAddress, workers_list):
    worker_queue = RoundRobQueue(workers_list)
    return partial(_master_handler, bind, worker_queue)