from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
import urllib.parse
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """ASGI middleware that populates `scope['user']` from a JWT token."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only process websocket connections
        if scope["type"] != "websocket":
            return await self.app(scope, receive, send)

        token = None

        # 1) Try query string: ?token=...
        query_string = scope.get("query_string", b"").decode()
        logger.info(f"Query string: {query_string}")
        if query_string:
            qs = urllib.parse.parse_qs(query_string)
            if "token" in qs:
                token = qs["token"][0]
                logger.info(f"Token found in query string: {token[:20]}...")

        # 2) Try Authorization header: "Authorization: Bearer <token>"
        if not token:
            headers = dict(scope.get("headers", []))
            logger.info(f"Headers: {headers}")
            for key, value in headers.items():
                key_str = key.decode() if isinstance(key, bytes) else key
                value_str = value.decode() if isinstance(value, bytes) else value
                if key_str.lower() == "authorization":
                    if value_str.startswith("Bearer "):
                        token = value_str.split(" ", 1)[1]
                        logger.info(f"Token found in header: {token[:20]}...")
                    break

        # Validate token and set user
        if token:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = await self.get_user(validated_token)
                scope["user"] = user
                # Use email instead of username for CustomUser model
                user_identifier = getattr(user, 'email', getattr(user, 'id', 'unknown'))
                logger.info(f"User authenticated: {user.id} - {user_identifier}")
            except Exception as e:
                logger.error(f"JWT validation error: {e}")
                scope["user"] = AnonymousUser()
        else:
            logger.warning("No token provided in request")
            scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)

    @database_sync_to_async
    def get_user(self, validated_token):
        jwt_auth = JWTAuthentication()
        return jwt_auth.get_user(validated_token)