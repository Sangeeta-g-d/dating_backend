import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing
import ask_me_feature.routing  # ✅ NEW

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dating_backend.settings')
django.setup()

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns +   # existing chat routes
            ask_me_feature.routing.websocket_urlpatterns    # ✅ new askme routes
        )
    ),
})
