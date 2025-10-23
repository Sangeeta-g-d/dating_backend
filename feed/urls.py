from django.urls import path
from .views import *

urlpatterns = [
    path('add-post/', AddPostAPIView.as_view(), name='add-post'),
    path('matched-user-posts/', MatchedUserPostsAPIView.as_view(), name='matched-user-posts'),
    path('user-profile/<int:user_id>/', UserProfileAPIView.as_view(), name='user-profile'),
    path('like-toggle/<int:post_id>/', ToggleLikeAPIView.as_view(), name='toggle-like'),
    path('add-comment/<int:post_id>/',AddCommentAPIView.as_view(),name="add-comment")
]