from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/askme/(?P<question_id>\d+)/$', consumers.AskMeConsumer.as_asgi()),
    re_path(r'ws/questions/$', consumers.QuestionConsumer.as_asgi()),
]
