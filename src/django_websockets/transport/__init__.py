from concurrent import futures
import traceback

from django_websockets.utils import Atom
from django_websockets.groups import GroupMessage
from django_websockets.groups.backends import BaseGroupBackend
from django_websockets.transport.proto import wstransport_pb2_grpc, wstransport_pb2
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from typing import Any, Union
import grpc as sync_grpc
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


SERVER = Atom('SERVER')
CLIENT = Atom('CLIENT')
FORWARDER = Atom('FORWARDER')


class BaseTransportLayer(object):

    group_name_regex = re.compile(r"^[a-zA-Z\d\-_.]+$")
    invalid_name_error = (
        "{} name must be a valid unicode string containing only ASCII "
        + "alphanumerics, hyphens, underscores, or periods."
    )

    def __init__(self, backend: BaseGroupBackend, config: TransportConfig):
        self.__backend = backend
        self.__config = config
        self.__role: Atom = CLIENT
        self._namespace = ""
        self._workers_queue = None

    @property
    def role(self):
        return self.__role
    
    @role.setter
    def role(self, role: Atom):
        if role in [SERVER, CLIENT, FORWARDER]:
            self.__role = role   

    @property
    def config(self) -> TransportConfig:
        return self.__config

    @property
    def backend(self) -> BaseGroupBackend:
        return self.__backend


    async def group_add(self, group, consumer):
        assert self.valid_group_name(group), "Invalid group name"
        await self.backend.group_add(group, consumer)

    async def group_discard(self, group, consumer):
        await self.backend.remove_group(group, consumer)

    async def group_send(self, group: str, message: Union[dict, GroupMessage]):
        # Ensure that message is a GroupMessage
        if not isinstance(message, GroupMessage):
            message = GroupMessage(**message)

        await self.backend.group_message(group, message)

    def match_type_and_length(self, name):
        if isinstance(name, str) and (len(name) < 100):
            return True
        return False
    
    def valid_group_name(self, name):
        if self.match_type_and_length(name):
            if bool(self.group_name_regex.match(name)):
                return True
        raise TypeError(
            "Group name must be a valid unicode string containing only ASCII "
            + "alphanumerics, hyphens, or periods."
        )

    @property
    def as_forwarder(self):
        self.__role = FORWARDER
        return self

    @property
    def as_server(self):
        self.__role = SERVER
        return self

    @property
    def as_client(self):
        self.__role = CLIENT
        return self

    async def __call__(self, namespace=None, workers_queue=None):
        raise NotImplementedError("This transport manager is not a callable corroutine")



class gRPCRoudRobStub(object):

    def __init__(self, address, workers_queue):
        self.address = address
        self._workers_queue = workers_queue
        self._stubs = {}


    def get_namespaced_address(self, namespace):
        address = self.address
        if namespace != "master":
            if address.endswith('.socket'):
                address = address[:-6]
                address = f'{address}{namespace}.socket'
            elif address.endswith('.sock'):
                address = address[:-4]
                address = f'{address}{namespace}.sock'
            else:
                address = f'{address}{namespace}.socket'
        return address
    
    async def SendMessage(self, request, context):
        if self._workers_queue:
            for worker in self._workers_queue:
                if worker in self._stubs:
                    stub = self._stubs[worker]
                else:
                    address = self.get_namespaced_address(worker)
                    conn = grpc.insecure_channel(address)
                    stub = wstransport_pb2_grpc.WSGroupManagerStub(conn)
                    self._stubs[worker] = stub
                await stub.SendMessage(request)
                    
            return wstransport_pb2.WSResponse(ack=True)

        return wstransport_pb2.WSResponse(ack=False)


class gGPCTransportLayer(BaseTransportLayer, wstransport_pb2_grpc.WSGroupManagerServicer):

    #backend: BaseGroupBackend
    __connection = None
    __stub = None

    @property
    def num_connections(self):
        return self.config.num_connections or 20
    
    @property
    def address(self):
        address = self.config.address or "unix:/tmp/rpc.socket"
        if self.role is SERVER:
            if self._namespace and self._namespace != "master":
                if address.endswith('.socket'):
                    address = address[:-6]
                    address = f'{address}{self._namespace}.socket'
                elif address.endswith('.sock'):
                    address = address[:-4]
                    address = f'{address}{self._namespace}.sock'
                else:
                    address = f'{address}{self._namespace}.socket'
        return address
    
    @property
    def graceful(self):
        return self.config.num_connections or 0
    
    async def SendMessage(self, request, context):
        message = GroupMessage(
            request.message.type,
            request.message.message
        )

        try:
            if self.role is FORWARDER:
                return await self.forward_stub.SendMessage(request, context)
            else:
                await super().group_send(request.group, message)
        except:
            traceback.print_exc()
            return wstransport_pb2.WSResponse(ack=False)
        else:
            return wstransport_pb2.WSResponse(ack=True)

    @property
    def forward_stub(self):
        if self._workers_queue:
            if not hasattr(self, '_forward_stub'):
                address = self.config.address or "unix:/tmp/rpc.socket"
                self._forward_stub = gRPCRoudRobStub(
                    address, self._workers_queue)
        return getattr(self, '_forward_stub', None)

    @property
    def stub(self):
        # The connection and stub are created lazily.
        # It's necessary to access self.connection to ensure
        # it's instantiate
        self.connection
        return self.__stub
    
    @property
    def connection(self):
        if self.__connection:
            return self.__connection
        
        if self.role in [SERVER, FORWARDER]:
            self.__connection = grpc.server(
                futures.ThreadPoolExecutor(max_workers=self.num_connections))
            self.__connection.add_insecure_port(self.address)
            self.__stub = wstransport_pb2_grpc.add_WSGroupManagerServicer_to_server(
                self, self.__connection)
        else:
            self.__connection = sync_grpc.insecure_channel(self.address)
            self.__stub = wstransport_pb2_grpc.WSGroupManagerStub(self.__connection)
        return self.__connection
    

    async def group_send(self, group:str, message:Union[dict, GroupMessage]):
        '''
        Broadcast a message 
        '''

        # If its a SERVER, we don't need to call RPC
        # (What about horizontaly scaling???)
        if self.role is SERVER:
            return await super().group_send(group, message)
        
        elif self.role is FORWARDER:
            self.forward_stub.SendMessage(
                wstransport_pb2.WSSendMessageRequest(
                    group=group,
                    message=wstransport_pb2.WSMessage(
                        **message
                    )))
        
        else:
            self.stub.SendMessage(
                wstransport_pb2.WSSendMessageRequest(
                    group=group,
                    message=wstransport_pb2.WSMessage(
                        **message
                    )))
    
    async def __call__(self, namespace, workers_queue=None):
        try:
            self._namespace = namespace
            self._workers_queue = workers_queue
            if self.role in [SERVER, FORWARDER]:
                self.__connection = None
                await self.connection.start()
                await self.connection.wait_for_termination()
                return 'ok'

            return self.role
        except Exception as e:
            return e

    async def stop(self):
        if self.role in [SERVER, FORWARDER]:
            self.connection.stop()


def get_channel_layer(using='default') -> BaseTransportLayer:
    """
    Returns a channel layer by alias, or None if it is not configured.
    """
    try:
        return channel_layers[using]
    except KeyError:
        return None


channel_layers = TransportManager()
