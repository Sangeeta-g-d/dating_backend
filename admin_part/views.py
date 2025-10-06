from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login,logout
from django.http import JsonResponse
from .models import *
# Create your views here.

def admin_dashboard(request):
    return render(request,'admin_dashboard.html')

def admin_login(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            # Optional: Check if user is admin
            if not user.is_staff:
                return JsonResponse({"status": "error", "message": "You are not authorized to access admin panel."})

            login(request, user)

            # Handle "Remember Me" — session expiry
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Expires on browser close

            return JsonResponse({"status": "success", "message": "Login successful! Redirecting..."})
        else:
            return JsonResponse({"status": "error", "message": "Invalid email or password."})

    return render(request, "admin_login.html")

# interests
def interests(request):
    interests = Interest.objects.all().order_by('name')

    if request.method == "POST":
        action = request.POST.get("action")

        # Add new interest
        if action == "add":
            name = request.POST.get("name", "").strip()
            if not name:
                return JsonResponse({"status": "error", "message": "Please enter a valid interest name."})
            
            if Interest.objects.filter(name__iexact=name).exists():
                return JsonResponse({"status": "error", "message": "This interest already exists."})

            Interest.objects.create(name=name)
            return JsonResponse({"status": "success", "message": "Interest added successfully!"})

        # Delete interest
        elif action == "delete":
            interest_id = request.POST.get("id")
            try:
                interest = Interest.objects.get(id=interest_id)
                interest.delete()
                return JsonResponse({"status": "success", "message": "Interest deleted successfully!"})
            except Interest.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Interest not found."})

    return render(request, 'interests.html', {"interests": interests})

# add subscription plans
def add_subscription_plan(request):
    if request.method == "POST":
        try:
            name = request.POST.get("name", "").strip()
            plan_type = request.POST.get("plan_type")
            price = request.POST.get("price", 0)
            duration_days = request.POST.get("duration_days", 0)
            swipe_limit = request.POST.get("swipe_limit") or None
            features = request.POST.getlist("features[]")  # multiple values
            is_active = request.POST.get("is_active") == "true"

            if not name:
                return JsonResponse({"status": "error", "message": "Name is required."})

            plan = SubscriptionPlan.objects.create(
                name=name,
                plan_type=plan_type,
                price=price,
                duration_days=duration_days,
                swipe_limit=swipe_limit,
                features=features,
                is_active=is_active,
            )
            return JsonResponse({"status": "success", "message": "Plan added successfully!"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return render(request, "add_subscription_plan.html")


def logout_view(request):
    logout(request)
    return redirect('admin_login')