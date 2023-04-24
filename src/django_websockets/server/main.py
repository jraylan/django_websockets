import asyncio
from multiprocessing import Event, Manager
import multiprocessing
import re
import time
import traceback
from typing import Dict
import signal
import websockets
import sys
import os
from django_websockets.middlewares.utils import database_sync_to_async
import django_websockets.server.arguments as arguments
from django_websockets.server.handler import connection_handler, master_handler
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import queues

# Fix multiprocessing error
try:
    queues.SimpleQueue
except:
    queues.SimpleQueue = queues.Queue


def __main(bind: arguments.WebsocketBindAddress, handler, settings=None, namespace="", workers_list=None):

    from django_websockets.transport import get_channel_layer, channel_layers
    
    async def run():
        loop = asyncio.get_running_loop()
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
                    handler, bind.address, bind.port + worker_index, loop=loop)
            else:
                target = f"{bind.address}:{bind.port}"
                server = websockets.serve(
                    handler, bind.address, bind.port, loop=loop)
                

        
        print(f'running {namespace} at {target}')

        def run_channel_layer(layer):
            if namespace == 'master':
                return get_channel_layer(using=layer).as_forwarder(namespace=namespace, workers_queue=workers_list)
            else:
                return get_channel_layer(using=layer).as_server(namespace=namespace)

        try:
            async with server:
                futures_stack = [
                    run_channel_layer(layer)
                    for layer in channel_layers
                ]
                await asyncio.gather(*futures_stack, return_exceptions=True)

        except asyncio.CancelledError:
            pass

        print(f"leaving {namespace}...")

    has_event_loop = False

    try:
        asyncio.get_running_loop()
        has_event_loop = True
    except:
        pass


    if namespace and not has_event_loop:
        try:
            return asyncio.run(run())
        except:
            traceback.print_exc()
            raise
        
    return run()


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


async def __start(loop:asyncio.BaseEventLoop, bind: arguments.WebsocketBindAddress, settings, workers: int, stop_event:Event):

    from django.conf import settings

    workers_map: Dict[str, asyncio.Future] = {}

    master_worker: asyncio.Future = None
    master_worker_namespace = 'master'

    
    process_manager = Manager()

    workers_list = process_manager.list(workers_map.keys())
    try:
        while not stop_event.get('stoped'):
            # has master started?
            if master_worker:
                # isn't master running?
                if master_worker.cancelled() or master_worker.done():
                    master_worker = loop.create_task(
                        __main(bind, master_handler(bind, workers_list), settings, master_worker_namespace, workers_list))
                    continue
            else:
                # start master
                master_worker = loop.create_task(
                    __main(bind, master_handler(bind, workers_list), settings, master_worker_namespace, workers_list))
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
                    loop, None, bind, connection_handler, settings, namespace, workers_list)
            else:
                for namespace in workers_map.keys():
                    if namespace not in workers_list:
                        workers_list.append(namespace)

                await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass

    print("Canceling master")
    for n, w in workers_map.items():
        print("Canceling {}".format(n))
        w.cancel()
    master_worker.cancel()



def main(bind: arguments.WebsocketBindAddress, settings=None, workers=1):
    if settings:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)
        django.setup()
    
    if workers == 1:
        return __main(bind, connection_handler)
    
    stop_event =  {}

    executor = ProcessPoolExecutor(max_workers=workers)

    started_at = time.time()
    
    def stop(task: asyncio.Task):
        print("stoping...")
        stop_event['stoped'] =  True
        print("stop event set")
        executor.shutdown(wait=False, cancel_futures=True)

        runing_time = time.time() - started_at
        if runing_time > 0 and runing_time < 10:
            # Wait all multiprocess spawn before kill
            time.sleep(10 - runing_time)
        
        for children in multiprocessing.active_children():
            os.kill(children.pid, signal.SIGKILL)

        print("loop stop scheduled")
        sys.exit(0)


    loop = asyncio.new_event_loop()
    loop.set_default_executor(executor)
    try:
        task = loop.create_task(__start(loop, bind, settings, workers, stop_event))
        for sig in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(sig, stop, task)
        loop.run_forever()
    except:
        executor.shutdown()
