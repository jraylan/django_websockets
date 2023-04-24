import asyncio
from functools import partial
from typing import Dict, NoReturn, Set
import warnings
from django_websockets.consumers import BaseConsumer

from django_websockets.groups import GroupMessage

class BaseGroupBackend(object):
    __group_listeners_lock: asyncio.Lock = asyncio.Lock()
    __group_listeners: Dict[str, Set[asyncio.Queue]] = {}

    def __init__(self, prefix=""):
        self.__prefix = prefix or ""

    def __get_group_name(self, group_base_name):
        """
        Wraps group name with a prefix to prevent name clash
        """
        return f'{self.__prefix}.__group.{group_base_name}'
    
    async def __on_stop(self, group_name, queue: asyncio.Queue()):
        """
        Removes the queue from the group listeners
        """
        print("onStop {}".format(group_name))
        async with self.__group_listeners_lock:
            # Was group even created?
            if group_name not in self.__group_listeners:
                return

            # Is group empty?
            if self.__group_listeners[group_name]:
                return
            
            try:
                self.__group_listeners[group_name].remove(queue)
            except KeyError:
                pass

    async def group_add(self, group_name: str, consumer: BaseConsumer) -> NoReturn:
        """
        Create a group if not exists then makes consumer listen to it
        """

        # Wraped group name
        group_name = self.__get_group_name(group_name)
        
        async with self.__group_listeners_lock:
            if group_name not in self.__group_listeners:
                self.__group_listeners[group_name]: Set[asyncio.Queue] = set()
        
        queue = asyncio.Queue()
    
        # Callback to remove queue from list
        on_stop = partial(self.__on_stop, group_name, queue)

        self.__group_listeners[group_name].add(queue)
        
        response = await consumer._listen_to_group(group_name, queue, on_stop)
        # if consumer returns false, call on_stop()
        if not response:
            await on_stop()

    async def remove_group(self, group_name: str, consumer: BaseConsumer) -> NoReturn:
        """
        Make consumer stop listening go a group and remove the group queue
        """

        # Wraped group name
        group_name = self.__get_group_name(group_name)

        async with self.__group_listeners_lock:
            try:
                await consumer._stop_listen_to_group(group_name, False)
                await self.__on_stop(group_name, consumer)
            except RuntimeError:
                pass

    async def group_message(self, name, message: GroupMessage):
        """
        Send message put the message in all queues from a group
        """

        # Wraped group name
        group_name = self.__get_group_name(name)

        if group_name not in self.__group_listeners:
            warnings.warn(
                "Sending a message for a not existing group {}".format(name))
            return
        
        if not self.__group_listeners[group_name]:
            warnings.warn(
                "Empty group listener {}".format(name))
            return


        for queue in self.__group_listeners[group_name]:
            await queue.put(message)
