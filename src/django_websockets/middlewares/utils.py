from asgiref.sync import SyncToAsync
from django.db import close_old_connections
from http.cookies import _unquote
from websockets.server import WebSocketServerProtocol


def get_cookie(websocket: WebSocketServerProtocol):
    cookies_data = {}

    for cookie in websocket.request_headers.get('Cookie', "").split(';'):
        if "=" in cookie:
            key, val = cookie.split('=', 1)
        else:
            key, val = "", cookie
        key = key.strip()
        if key:
            val = val.strip()
            val = val.split('\n')[0]
            val = _unquote(val)
            cookies_data[key] = val

    return cookies_data


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
