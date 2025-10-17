"""
ASGI config for dating_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""
import os
import django
from django.core.asgi import get_asgi_application

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dating_backend.settings')

# Configure Django BEFORE importing any modules that might use settings
django.setup()

# Now import the routing modules (they will have access to configured settings)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing

# Standard Django ASGI application
django_asgi_app = get_asgi_application()

# Channels routing
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})