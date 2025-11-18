from django.urls import path

from .views import *


urlpatterns = [
    path('rooms/',ChatRoomHistoryAPIView.as_view(),name="rooms")

]