from django.urls import path
from .views import *

urlpatterns = [
    path("register/", UserRegistrationAPIView.as_view(), name="user-register"),
    path("login/", UserLoginAPIView.as_view(), name="user-login"),
    path("send-otp/", SendOTPAPIView.as_view(), name="send-otp"),
    path("verify-otp/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("fetch-interests/",InterestListAPIView.as_view(),name="fetch-interests"),
    path("add-user-details/",UserProfileAPIView.as_view(),name="user-details"),
    path('update-fcm-token/', UpdateFCMTokenAPIView.as_view(), name='update_fcm_token'),
    path('refresh-token/', RefreshAccessTokenAPIView.as_view(), name='token_refresh'),
    path('user_profile/', UserDetailsProfileAPIView.as_view(), name='user_profile'),
    path('user-post/', UserFeedAPIView.as_view(), name='user_posts'),
    path('user-post/<int:pk>/', UserFeedAPIView.as_view(), name='delete-post'),


    path('search-users/', UserSearchAPIView.as_view(), name='search_users'),
]