from django.urls import path
from .views import *

urlpatterns = [
    # Fetch potential matches for swipe
    path('swipe-users/', SwipeUsersAPIView.as_view(), name='swipe-users'),
    # Perform a swipe (like/dislike)
    path('swipe-action/', SwipeAPIView.as_view(), name='swipe-action'),

    # received match request
    path('match-requests/', ReceivedMatchRequestsAPIView.as_view(), name='match-requests-list'),
    # Accept or reject a match request
    path('match-request-action/<int:request_id>/', SwipeActionAPIView.as_view(), name='match-request-action'),
    # Get list of confirmed matches
    path('matches/', MatchesListAPIView.as_view(), name='matches-list'),
]