from django.urls import path
from . import views

urlpatterns = [
    path('admin_dashboard/',views.admin_dashboard,name="admin_dashboard"),
    path('admin_login/',views.admin_login,name="admin_login"),
    path('logout/',views.logout_view,name="logout"),
    path('interests/',views.interests,name="interests"),
    path('add_subscription_plan/',views.add_subscription_plan,name="add_subscription_plan"),
]