from django.urls import path
from . import views

urlpatterns = [
    path('admin_dashboard/',views.admin_dashboard,name="admin_dashboard"),
    path('admin_login/',views.admin_login,name="admin_login"),
    path('logout/',views.logout_view,name="logout"),
    path('interests/',views.interests,name="interests"),
    path('add_subscription_plan/',views.add_subscription_plan,name="add_subscription_plan"),
    path('subscription_plans/',views.subscription_plans,name="subscription_plans"),
    path("edit_subscription_plan/<int:plan_id>/", views.edit_subscription_plan, name="edit_subscription_plan"),
    path("delete_subscription_plan/<int:plan_id>/", views.delete_subscription_plan, name="delete_subscription_plan"),

    path('user_list/',views.user_list,name="user_list"),

]