# Django + Websockets

This project is a case study of using [Python Websockets](https://github.com/python-websockets/websockets) as a websocket backend for [Django](https://github.com/django/django).

It's inspired by [Django Channels](https://github.com/django/channels) and aims to provide a seamless transition from it, despite not being an ASGI implementation.


## Motivation
Although Django Channels is easy to use and offers excellent performance in single-group or groupless environments, its performance tends to drop significantly in multi-group implementations. This approach uses a RPC transport for communication, eliminating the dependency on a message broker like Redis. Instead, we managed groups using asyncio queues.


## Configuration Example

#### settings.py

```py

# Middleware stack called in each connection
WEBSOCKET_MIDDLEWARE = [
    'django_websockets.middlewares.scope.ScopeMiddleware',
    'django_websockets.middlewares.auth.AuthMiddleware',
    'django_websockets.middlewares.route.RouteMiddleware'
]


# URL mapping module path
WEBSOCKET_ROUTE_MODULE = 'my_project.routing'

# Transport backend
WEBSOCKET_TRANSPORT_BACKENDS = {
    'default': {
        'BACKEND': 'django_websockets.transport.gGPCTransportLayer',
        'CONFIG': {
            'address': 'unix:/tmp/example.sock'
        }
    }
}

```

#### my_project/routing.py
```py

from django.urls import re_path

from myapp.websockets import (
    InternalChatConsumer
)

urlpatterns = [
    re_path(r'/ws/internalchat/?$',
            ChatConsumer.as_handler()),
]
```

#### myapp/websockets.py
```py

from django_websockets.groups import GroupMessage
from django_websockets.consumers import BaseConsumer
from django_websockets.middlewares.utils import database_sync_to_async
from django_websockets.transport import get_channel_layer
import json

class ChatConsumer(BaseConsumer):

    session_started = False

    async def connect(self):
        # Channels like scope system
        self.user = self.scope["user"]

        if not await database_sync_to_async(self.user.has_perm)('myapp.connect_to_chat'):
            return await self.reject()
            
        self.room_group_name = f'chat_room_a'
        self.user_name = self.user.name or self.user.user_name,

        await get_channel_layer().group_add(
            self.room_group_name,
            self
        )

        session_started = True

    async def reject(self):
        # Do any cleaning here
        await self.close()

    async def chat_message(self, event:GroupMessage):
        # Params can be used for doing filtering

        params = json.loads(event.params)
        if params['user_name'] === self.user_name:
            return

        await self.send(json.dumps({
            'from': params['user_name'],
            'message': event.message}))

    async def receive(self, text_data):
        # User was verified?
        if self.session_started:
            await get_channel_layer().group_send(
                 self.room_group_name,
                 GroupMessage(
                     'chat_message',
                     message=text_data,
                     params=json.dumps({'sender': self.user_name})
                 )
            )

```


### Running

#### Using TCP:
```bash
python3 manage.py websockets_server -b localhost:7000 -w 4
```

#### Using Unix:
```bash
python3 manage.py websockets_server -b unix:/var/run/websockets.sock -w 4
```

