from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
import urllib.parse


class JWTAuthMiddleware:
    """ASGI middleware that populates `scope['user']` from a JWT token.

    It looks for the token in the websocket querystring as `?token=...` or
    in the `authorization` header as `Bearer <token>`.

    Usage: wrap your websocket application with `JWTAuthMiddleware(...)` in
    `asgi.py`.
    """

    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope):
        return JWTAuthMiddlewareInstance(scope, self.inner)


class JWTAuthMiddlewareInstance:
    def __init__(self, scope, inner):
        self.scope = dict(scope)
        self.inner = inner

    async def __call__(self, receive, send):
        token = None

        # 1) Try query string: ?token=...
        query_string = self.scope.get("query_string", b"").decode()
        if query_string:
            qs = urllib.parse.parse_qs(query_string)
            if "token" in qs:
                token = qs["token"][0]

        # 2) Try Authorization header: "Authorization: Bearer <token>"
        if not token:
            headers = {k.decode(): v.decode() for k, v in self.scope.get("headers", [])}
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                token = auth.split(" ", 1)[1]

        # Validate token and set user
        if token:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = jwt_auth.get_user(validated_token)
                self.scope["user"] = user
            except Exception:
                self.scope["user"] = AnonymousUser()
        else:
            self.scope["user"] = AnonymousUser()

        inner = self.inner(self.scope)
        return await inner(receive, send)


# Helper to wrap AuthMiddlewareStack with JWT lookup easily if needed
def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
