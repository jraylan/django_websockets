import asyncio
from multiprocessing import Manager
import re
import traceback
from typing import Dict
import websockets
from django_websockets.middlewares.utils import database_sync_to_async
import django_websockets.server.arguments as arguments
from django_websockets.server.horchestration import RoundRobQueue
from django_websockets.server.handler import connection_handler, master_handler
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import queues

# Fix multiprocessing error
try:
    queues.SimpleQueue
except:
    queues.SimpleQueue = queues.Queue


def __main(bind: arguments.WebsocketBindAddress, handler, settings=None, namespace="", workers_list=None):

    from django_websockets.transport import get_channel_layer, channel_layers
    
    async def run():

        if settings:
            import django
            import os

            if not django.apps.apps.ready:
                try:
                    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)
                    await database_sync_to_async(django.setup)()
                except:
                    traceback.print_exc()
    
        address: str = bind.address
        if bind.is_unix:
            address = bind.get_namespaced_address(namespace)
            target = address
            server = websockets.unix_serve(
                handler, path=address)
        else:
            if namespace:
                try:
                    worker_index = int(re.sub(r'[^0-9]', '', namespace)) + 1
                except ValueError:
                    worker_index = 0
                    
                target = f"{bind.address}:{bind.port + worker_index}"
                server = websockets.serve(
                    handler, bind.address, bind.port + worker_index)
            else:
                target = f"{bind.address}:{bind.port}"
                server = websockets.serve(
                    handler, bind.address, bind.port)
                

        
        print(f'running {namespace} at {target}')

        async def run_channel_layer(layer):
            if namespace == 'master':
                return await get_channel_layer(using=layer).as_forwarder(namespace=namespace, workers_queue=workers_list)
            else:
                return await get_channel_layer(using=layer).as_server(namespace=namespace)
            
        async with server:
            result = await asyncio.gather(*[
                run_channel_layer(layer)
                for layer in channel_layers
            ])

        print(result)
        print(f"leaving {namespace}...")
    if namespace:
        try:
            return asyncio.run(run())
        except:
            traceback.print_exc()
            raise
    
    run()


def _start_worker(loop, executor, bind, handler, settings, namespace, workers_list):
    print(f"starting {namespace}...")
    return loop.run_in_executor(
        executor,
        __main,
        bind,
        handler,
        settings,
        namespace,
        workers_list
    )


async def __start(loop, bind: arguments.WebsocketBindAddress, settings, workers: int):

    from django.conf import settings

    workers_map: Dict[str, asyncio.Future] = {}
    num_workers = workers +1

    master_worker: asyncio.Future = None
    master_worker_namespace = 'master'

    
    process_manager = Manager()

    workers_list = process_manager.list(workers_map.keys())
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        while True:
            # has master started?
            if master_worker:
                # isn't master running?
                if master_worker.cancelled() or master_worker.done():
                    master_worker = _start_worker(
                        loop, executor, bind, master_handler(bind, workers_list), settings, master_worker_namespace, workers_list)
                    continue
            else:
                # start master
                master_worker = _start_worker(
                    loop, executor, bind, master_handler(bind, workers_list), settings, master_worker_namespace, workers_list)
                continue

            for i in range(workers):
                namespace = f'worker_{i}'

                if namespace in workers_map:
                    if workers_map[namespace].cancelled() or workers_map[namespace].done():
                        break
                    namespace = None
                else:
                    break

            if namespace:
                workers_map[namespace] = _start_worker(
                    loop, executor, bind, connection_handler, settings, namespace, workers_list)
            else:
                for namespace in workers_map.keys():
                    if namespace not in workers_list:
                        workers_list.append(namespace)

                await asyncio.sleep(2)



def main(bind: arguments.WebsocketBindAddress, settings=None, workers=1):
    if settings:
        import django
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)
        django.setup()
    
    if workers == 1:
        return __main(bind, connection_handler)
    
    loop = asyncio.new_event_loop()
    loop.create_task(__start(loop, bind, settings, workers))
    loop.run_forever()
    