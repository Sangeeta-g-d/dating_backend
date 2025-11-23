from django.urls import path
from .views import *

urlpatterns = [

    path('add-story/',UploadStoryAPIView.as_view(),name="add-story"),
    path('fetch-stories/',FetchStoriesAPIView.as_view(),name="fetch-stories"),
    path('view-story/<int:story_id>/', MarkStoryViewedAPIView.as_view(), name='mark-story-viewed'),
    path('delete-story/<int:story_id>/', DeleteStoryAPIView.as_view(), name='delete_story'),
    path('story-viewers/<int:story_id>/', StoryViewersAPIView.as_view(), name='story_viewers'),
]

