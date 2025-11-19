from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
import urllib.parse
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


class JWTAuthMiddleware(BaseMiddleware):
    """ASGI middleware that populates `scope['user']` from a JWT token."""

    async def __call__(self, scope, receive, send):
        token = None

        # Only process websocket connections
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        # 1) Try query string: ?token=...
        query_string = scope.get("query_string", b"").decode()
        if query_string:
            qs = urllib.parse.parse_qs(query_string)
            if "token" in qs:
                token = qs["token"][0]

        # 2) Try Authorization header: "Authorization: Bearer <token>"
        if not token:
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                token = auth.split(" ", 1)[1]

        # Validate token and set user
        if token:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = await self.get_user(validated_token)
                scope["user"] = user
            except Exception as e:
                print(f"JWT validation error: {e}")
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, validated_token):
        jwt_auth = JWTAuthentication()
        return jwt_auth.get_user(validated_token)