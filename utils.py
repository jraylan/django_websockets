from http.cookies import SimpleCookie
from websockets.server import WebSocketServerProtocol


def get_cookie(websocket: WebSocketServerProtocol):
    cookies = websocket.request_headers.get('Cookie')
    return SimpleCookie(cookies or "")
    
