import inspect
import traceback
from typing import AsyncIterable, Awaitable, Callable, Dict, Iterable, Set, Type, Union
import warnings
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.typing import Data
import asyncio
import functools
from django_websockets.groups import GroupMessage
from django_websockets.utils import async_partial


class StopConsumer(Exception): ...


class BaseConsumer(object):
    """
    Base Consumer class
    """

    consumer_class: Type["BaseConsumer"]

    # Maps all queues that this consumer is listening
    # and the listening task it self
    __group_lock: asyncio.Lock = asyncio.Lock()
    __group_queues: Dict[str, asyncio.Queue] = dict()
    __group_callbacks: Dict[str, Awaitable[Callable[...,bool]]] = dict()

    def get_process_message_timeout(self) -> int:
        """
        Deadline for processing group message
        """
        return 0


    @property
    def __process_message_timeout(self):
        try:
            return int(self.get_process_message_timeout())
        except:
            return 0

    async def __process(self, message: GroupMessage):
        if not isinstance(message, GroupMessage):
            try:
                message = GroupMessage(**message)
            except:
                warnings.warn(
                    "Consumer '{}' received a group message that is not a instance of 'GroupMessage'"
                    .format(
                        self.__class__.__name__
                    ))
                return

        method = getattr(self, message.type, None)
        if not method or \
           not inspect.iscoroutinefunction(method) \
           or len(inspect.signature(method).parameters.keys()) != 1:
            warnings.warn(
                "Consumer '{}' received a group message of type '{}' but doesn't have a async method with this name that receives a Union[str|bytes]"
                .format(
                    self.__class__.__name__,
                    message.type
                ))
            return
        try:
            await method({**message})
        except Exception as e:
            traceback.print_exc()
            warnings.warn(
                "a unhandled exception ocurred while processing message of type '{}' on consummer '{}':\n\t{}"
                .format(self.__class__.__name__,
                        message.type,
                        str(e))
            )

    async def _listen_to_group(self, group_name:str, group_queue: asyncio.Queue, on_stop: Awaitable[Callable]) -> bool:
        """
        Adds start a queue listening task and add it to the groups and listeners maps.
        Returns false if already listening and true otherwise
        """
        
        async with self.__group_lock:
            if self.__closing:
                # Consumer is closing, so return false to make the queue to be removed
                warnings.warn('Trying go add a closing connection to group.')
                return False
            
            # check if already listening
            if group_name in self.__group_queues:
                if self.__group_queues[group_name]:
                    # Check if the queue is the same
                    if self.__group_queues[group_name] == group_queue:
                        return True
                    else:
                        return False
                else:
                    # For some reason its empty, só add the new queue
                    self.__group_queues[group_name] = group_queue
                    return True
            
            self.__group_queues[group_name] = group_queue
            self.__group_callbacks[group_name] = on_stop
            
        return True

    async def _stop_listen_to_group(self, group_name:str):
        """
        Pop the task from the groups and listeners maps and wait for the task to finish
        """
        callback = None
        async with self.__group_lock:
            callback = self.__group_callbacks.pop(group_name, None)
            self.__group_queues.pop(group_name, None)
            
        if callback:
            await asyncio.wait_for(callback(), timeout=1)
        
        return group_name

        
    async def __dispose(self):
        """
        Mark consumer as closing and cleanup all tasks
        """
        self.__closing = True

        async with self.__group_lock:
            tasks = [self._stop_listen_to_group(group_name)
                     for group_name in self.__group_queues]
            
        await asyncio.gather(
            *tasks,
            return_exceptions=False)
        raise StopConsumer
        
    async def dispose(self):
        """
        Mark consumer as closing and cleanup all tasks
        """
        await self.__dispose()


    async def connect(self, scope, *args, **kwargs):
        """
        The entry point of the consumer. It receives the scope of the connection and the url args/kwargs.
        Closes the connection if any excepion is raised.
        """
        raise NotImplementedError("Async method connect(scope, *args, **kwargs) must be implemented")
    
    async def receive(self, data:Union[str, bytes]):
        """
        Called when a new message is received from the client.
        Closes the connection if any excepion is raised.
        """
        raise NotImplementedError(
            "Async method receive(self, data) must be implemented")
    
    async def close(self):
        if not self.__closing:
            await self.dispose()
    
    async def __recv(self, websocket: WebSocketServerProtocol):
        """
        Waits for messages from client and dispatches it's content to receive(self, data).
        """
        if not asyncio.iscoroutinefunction(self.receive):
            raise TypeError(
                "method receive(self, data) must be a corroutine")

        while not self.__closing:
            try:
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=0.1
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    continue
                else:
                    await self.receive(message)
            except websockets.ConnectionClosed:
                return
            except:
                traceback.print_exc()

    async def __process_group(self, group_name):
        try:
            if group_name not in self.__group_queues:
                warnings.warn(
                    "Processing a group that has no queue {}".format(group_name))
                return
            
            queue = self.__group_queues[group_name]
            message = await asyncio.wait_for(
                queue.get(),
                timeout=1
            )
            await self.__process(message)
            
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            return
        except:
            traceback.print_exc()
        

    async def __recv_group(self):
        """
        Wait for messages on the queue and processes it
        """

        try:
            # Store the groups handled in each interation
            running_groups: Set[str] = set()

            while not self.__closing:
                try:
                    # Make a copy of all current groups name
                    async with self.__group_lock:
                        for group_name in self.__group_queues.keys():
                            running_groups.add(group_name)

                    if not running_groups:
                        await asyncio.sleep(0.1)
                        continue

                    # Execute ther recv for every group
                    await asyncio.gather(
                        *[self.__process_group(group_name) for group_name in running_groups],
                        return_exceptions=False)

                    # Get the list of groups that needs to be removed
                    async with self.__group_lock:
                        groups_to_remove = [
                            group_name
                            for group_name in running_groups
                            if group_name not in self.__group_queues
                        ]

                    if groups_to_remove:
                        # Cleanup groups
                        for removed_group in await asyncio.gather(*[
                            self._stop_listen_to_group(group_name) for group_name in groups_to_remove],
                            return_exceptions=False):

                            running_groups.remove(removed_group)
                except asyncio.CancelledError:
                    pass
                except:
                    traceback.print_exc()
                        
        except:
            traceback.print_exc()
        finally:
            # Stores the groups to prevent deathlock
            async with self.__group_lock:
                groups = list(self.__group_queues.keys())

            await asyncio.gather(
                *[self._stop_listen_to_group(group_name)
                  for group_name in groups],
                  return_exceptions=False
            )

    async def __call__(self, websocket: WebSocketServerProtocol, *args, **kwargs):
        if not asyncio.iscoroutinefunction(self.connect):
            raise TypeError(
                "method connect(scope, *args, **kwargs) must be a corroutine")
        self.__closing = False
        self.scope = websocket.scope
        group_task = asyncio.create_task(self.__recv_group())
        try:
            await self.connect()
            await self.__recv(websocket)
        except StopConsumer:
            pass            
        finally:
            traceback.print_exc()
            group_task.cancel()
            await self.close()
            while not group_task.done():
                await asyncio.sleep(0.1)

    # Is it necessary?
    # Kept for channel compatibility
    async def accept(self): ...
        
    async def __send(self, websocket: WebSocketServerProtocol, text_data: Union[Data, Iterable[Data], AsyncIterable[Data]]):
        await websocket.send(text_data)

    async def send(
        message: Union[Data, Iterable[Data], AsyncIterable[Data]]): ...

    @classmethod
    def as_handler(cls, **initkwargs):

        async def app(websocket, *args, **kwargs):
            consumer = cls(**initkwargs)
            consumer.send = async_partial(consumer.__send, websocket)
            functools.update_wrapper(consumer.send, websocket.send)
            return await consumer(websocket, *args, **kwargs)

        app.consumer_class = cls
        app.consumer_initkwargs = initkwargs

        # take name and docstring from class
        functools.update_wrapper(app, cls, updated=())
        return app
