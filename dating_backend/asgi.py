import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dating_backend.settings")

# Initialize Django before importing anything that might use ORM
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from auth_api.jwt_middleware import JWTAuthMiddleware
import chat.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})