from asyncio import futures
from django_websockets.groups import GroupMessage
from django_websockets.groups.backends import BaseGroupBackend
from django_websockets.transport.proto import wstransport_pb2_grpc, wstransport_pb2
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from typing import Any
import asyncio
import grpc.aio as grpc
import re


class TransportConfig(dict):
    __inited = False

    def __init__(self, dict:dict):
        super(TransportConfig, self).__init__(dict)
        self.__inited = True
    
    def __getattr__(self, __name: str) -> Any:
        try:
            return self[__name]
        except:
            return None
        
    def __setattr__(self, __name: str, __value: Any) -> None:
        if self.__inited:
            raise SyntaxError('TransportConfig is readonly')
        super().__setattr__(__name, __value)

    def __setitem__(self, __key, __value) -> None:
        if self.__inited:
            return
        return super().__setitem__(__key, __value)


class TransportManager:
   
    __backends = {}

    def __getitem__(self, __key) -> None:
        try:
           return self.__backends[__key or 'default']
        except KeyError:
            RuntimeError(
                "TransportLayer with namespace '{}' not found".format(__key))

    def __init__(self):
        try:
            backend_config = settings.WEBSOCKET_TRANSPORT_BACKENDS
        except:
            raise ImproperlyConfigured(
                "'WEBSOCKET_TRANSPORT_BACKENDS' wasn't set on django settings.")
        else:

            if 'default' not in backend_config:
                raise ImproperlyConfigured(
                    "'WEBSOCKET_TRANSPORT_BACKENDS' must have a 'default' item.")

            for namespace, config in backend_config.items():
                transport_layer = None
                try:
                    transport_layer = import_string(config['BACKEND'])
                except KeyError:
                    raise ImproperlyConfigured(
                        "'WEBSOCKET_TRANSPORT_BACKENDS' item must have a 'BACKEND'.")
                
                transport_config = None
                try:
                    transport_config = TransportConfig(config['CONFIG'])
                except KeyError:
                    raise ImproperlyConfigured(
                        "'WEBSOCKET_TRANSPORT_BACKENDS' item must have a 'CONFIG'.")

                self.__backends[namespace] = transport_layer(BaseGroupBackend(
                    prefix=transport_config.prefix or namespace), transport_config)

    def __iter__(self):
        return self.__backends.__iter__()
        

class BaseTransportLayer(object):    
    group_name_regex = re.compile(r"^[a-zA-Z\d\-_.]+$")
    invalid_name_error = (
        "{} name must be a valid unicode string containing only ASCII "
        + "alphanumerics, hyphens, underscores, or periods."
    )

    def __init__(self, backend: BaseGroupBackend, config: TransportConfig):
        self.__backend = backend
        self.__config = config

    @property
    def config(self) -> TransportConfig:
        return self.__config

    @property
    def backend(self) -> BaseGroupBackend:
        return self.__backend


    async def group_add(self, group, consumer):
        assert self.valid_group_name(group), "Invalid group name"
        self.backend.group_add(group, consumer)

    async def group_discard(self, group, consumer):
        self.backend.remove_group(group, consumer)

    async def group_send(self, group, message):
        await self.backend.group_message(group, message)

    def valid_group_name(self, name):
        if self.match_type_and_length(name):
            if bool(self.group_name_regex.match(name)):
                return True
        raise TypeError(
            "Group name must be a valid unicode string containing only ASCII "
            + "alphanumerics, hyphens, or periods."
        )
    
    async def __call__(self):
        raise NotImplementedError("This transport manager is not a callable corroutine")



class gRPCTransportLayerType:...


SERVER = gRPCTransportLayerType()
CLIENT = gRPCTransportLayerType()


class gGPCTransportLayer(BaseTransportLayer, wstransport_pb2_grpc.WSGroupManagerServicer):

    #backend: BaseGroupBackend
    __role = CLIENT
    __connection = None
    __stub = None

    @property
    def stub(self):
        return self.__stub

    @property
    def num_connections(self):
        return self.config.num_connections or 20
    
    @property
    def address(self):
        return self.config.address or "unix:/tmp/rpc.socket"
    
    @property
    def graceful(self):
        return self.config.num_connections or 0
    
    def SendMessage(self, request, context):
        print(request, context)

    @property
    def conenction(self):
        if self.__connection:
            return self.__connection
        
        if self.__role == SERVER:
            self.__connection = server = grpc.server(futures.ThreadPoolExecutor(
                max_workers=self.num_connections))
            self.__stub = wstransport_pb2_grpc.add_WSGroupManagerServicer_to_server(
                self, self.__connection)

            server.add_secure_port(self.address)
            return server
        
        self.__connection = grpc.insecure_channel(self.address)
        self.__stub = wstransport_pb2_grpc.WSGroupManagerStub(self.__connection)
        return self.conenction

    async def group_send(self, group, message):
        if self.__role == SERVER:
            return await super().group_message(group, GroupMessage(message['type'], message['message']))
        
        await self.stub.SendMessage(
            wstransport_pb2.WSMessage(
                **message
            )
        )

    async def __call__(self):
        self.__role = SERVER
        await self.connection.start()
        await self.connection.wait_for_termination()

    async def stop(self):
        if self.__role is SERVER:
            self.conenction.stop()


def get_channel_layer(using='default'):
    """
    Returns a channel layer by alias, or None if it is not configured.
    """
    try:
        return channel_layers[using]
    except KeyError:
        return None


channel_layers = TransportManager()
