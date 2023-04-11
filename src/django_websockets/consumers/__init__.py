import inspect
from typing import Awaitable, Callable, Dict, Type, Union
import warnings
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
import asyncio
import functools
from django_websockets.groups import GroupMessage

def app_behavior(app):
    async def wrapped_app(**kwargs):
        await app(**kwargs)

    return wrapped_app


class StopConsumer(Exception): ...


class BaseConsumer(object):
    """
    Base Consumer class
    """

    consumer_class: Type["BaseConsumer"]

    # Maps all queues that this consumer is listening
    # and the listening task it self
    __group_lock: asyncio.Lock = asyncio.Lock()
    __group_listeners: Dict[str, asyncio.Task] = {}
    __group_queues: Dict[str, asyncio.Queue] = {}

    async def __process(self, message: GroupMessage):
        if not isinstance(message, GroupMessage):
            warnings.warn(
                "Consumer '{}' received a group message that is not a instance of 'GroupMessage'"
                .format(
                    self.consumer_class.__name__
                ))
            return

        method = getattr(self, message.type, None)
        if not method or \
           not inspect.iscoroutinefunction(method) \
           or len(inspect.signature(method).parameters) is not 2:
            warnings.warn(
                "Consumer '{}' received a group message of type '{}' but doesn't have a async method with this name that receives a Union[str|bytes]"
                .format(
                    self.consumer_class.__name__,
                    message.type
                ))
            return
        content = message.message
        try:
            method(content)
        except Exception as e:
            warnings.warn(
                "Not handled exception ocurred while processing message of type '{}' on consummer '{}':\n\t{}"
                .format(self.consumer_class.__name__,
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
                return False
            
            # check if already listening
            if group_name in self.__group_listeners:
                # Check if listener exists is not cancelled
                if not self.__group_listeners[group_name].cancelled():
                    # Check if queue was saved
                    if self.__group_queues.get(group_name):
                        # Check if the queue is the same
                        if self.__group_queues[group_name] == group_queue:
                            return True
                        else:
                            return False
                    else:
                        # For some reason its empty, só add the new queue
                        self.__group_queues[group_name] = group_queue
                        return True
            
            self.__group_queues[group_queue] = group_queue
            self.__group_listeners[group_queue] = asyncio.create_task(
                self.__listen_to_group(group_name, group_queue, on_stop))
            
            return True

    async def __listen_to_group(self, group_name:str, group_queue: asyncio.Queue, on_stop: Awaitable[Callable]):
        """
        Wait for messages on the queue and processes it
        """
        try:
            while not self.__closing:
                async with self.__group_lock:
                    if group_name not in self.__group_listeners \
                    or group_name not in self.__group_queues:
                        break
                try:
                    message = await asyncio.wait_for(
                        group_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue
                else:
                    await self.__process(message)
        finally:
            await self._stop_listen_to_group(group_name, group_queue)
            await on_stop()

    async def _stop_listen_to_group(self, group_name:str):
        '''
        Pop the task from the groups and listeners maps and wait for the task to finish
        '''
        async with self.__group_lock:
            task = self.__group_listeners.pop(group_name, None)
            self.__group_queues.pop(group_name, None)
            
        if task:
            await asyncio.wait_for(task)

        
    async def __dispose(self):
        """
        Mark consumer as closing and cleanup all tasks
        """
        self.__closing = True

        async with self.__group_lock:
            tasks = [self._stop_listen_to_group(group_name)
                     for group_name in self.__group_listeners]
            
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
                except asyncio.TimeoutError:
                    continue
                else:
                    await self.receive(message)
            except:
                return

    async def __call__(self, websocket: WebSocketServerProtocol, *args, **kwargs):
        if not asyncio.iscoroutinefunction(self.connect):
            raise TypeError(
                "method connect(scope, *args, **kwargs) must be a corroutine")
        self.__closing = False
        await self.connect(websocket.scope, *args, **kwargs)
        await self.__recv(websocket)
        await self.close()

    @classmethod
    def as_handler(cls, **initkwargs):

        @app_behavior
        async def app(websocket, *args, **kwargs):
            consumer = cls(**initkwargs)
            return await consumer(websocket, *args, **kwargs)

        app.consumer_class = cls
        app.consumer_initkwargs = initkwargs

        # take name and docstring from class
        functools.update_wrapper(app, cls, updated=())
        return app
