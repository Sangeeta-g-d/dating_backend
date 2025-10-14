from django.urls import path
from .views import *

urlpatterns = [
    # Fetch potential matches for swipe
    path('swipe-users/', SwipeUsersAPIView.as_view(), name='swipe-users'),
    # Perform a swipe (like/dislike)
    path('swipe-action/', SwipeAPIView.as_view(), name='swipe-action'),
    # Accept or reject a match request
    path('match-request/<int:request_id>/', MatchRequestActionAPIView.as_view(), name='match-request-action'),
    # Get list of confirmed matches
    path('matches/', MatchesListAPIView.as_view(), name='matches-list'),
]