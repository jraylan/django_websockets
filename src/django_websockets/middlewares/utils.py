from asgiref.sync import SyncToAsync
from django.db import close_old_connections
from http.cookies import SimpleCookie
from websockets.server import WebSocketServerProtocol


def get_cookie(websocket: WebSocketServerProtocol):
    cookies = websocket.request_headers.get('Cookie')
    return SimpleCookie(cookies or "")


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections when it exits.
    """

    def thread_handler(self, loop, *args, **kwargs):
        close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            close_old_connections()


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync
