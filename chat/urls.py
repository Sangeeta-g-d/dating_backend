from django.urls import path
from .views import *

urlpatterns = [
    
    path("chat-room/", GetOrCreateChatRoomView.as_view(), name="chat-room"),

]