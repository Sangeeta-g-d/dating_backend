from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from auth_api.models import CustomUser
from swipe_feature.models import Match
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
            # is_active = request.POST.get("is_active") == "true"

            if not name:
                return JsonResponse({"status": "error", "message": "Name is required."})

            plan = SubscriptionPlan.objects.create(
                name=name,
                plan_type=plan_type,
                price=price,
                duration_days=duration_days,
                swipe_limit=swipe_limit,
                features=features,
                # is_active=is_active,
            )
            return JsonResponse({"status": "success", "message": "Plan added successfully!"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return render(request, "add_subscription_plan.html")

def subscription_plans(request):
    plans = SubscriptionPlan.objects.all().order_by('price')
    return render(request, "subscription_plans.html", {"plans": plans})


def edit_subscription_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    if request.method == "POST":
        try:
            plan.name = request.POST.get("name", "").strip()
            plan.plan_type = request.POST.get("plan_type")
            plan.price = request.POST.get("price", 0)
            plan.duration_days = request.POST.get("duration_days", 0)
            plan.swipe_limit = request.POST.get("swipe_limit") or None
            plan.features = request.POST.getlist("features[]")
            plan.is_active = request.POST.get("is_active") == "true"
            plan.save()

            return JsonResponse({"status": "success", "message": "Subscription plan updated successfully!"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return render(request, "edit_subscription_plan.html", {"plan": plan})

@csrf_exempt
def delete_subscription_plan(request, pk):
    if request.method == "DELETE":
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
            plan.delete()
            return JsonResponse({"status": "success", "message": "Plan deleted successfully!"})
        except SubscriptionPlan.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Plan not found."})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error", "message": "Invalid request method."})

def user_list(request):
    user_list = CustomUser.objects.exclude(is_superuser=True).order_by('-date_joined')

    per_page = request.GET.get('per_page', '10')
    try:
        per_page = int(per_page)
    except (ValueError, TypeError):
        per_page = 10

    if per_page not in [10, 20, 50, 100]:
        per_page = 10

    paginator = Paginator(user_list, per_page)
    page_number = request.GET.get('page', 1)

    try:
        users = paginator.page(page_number)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)

    total_users = user_list.count()
    blocked_users = user_list.filter(is_blocked=True).count()
    active_users = total_users - blocked_users
    total_matches = Match.objects.count()
    with_profile = user_list.filter(profile__isnull=False).count()

    context = {
        'users': users,
        'per_page': per_page,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'total_matches': total_matches,
        'with_profile': with_profile,
    }
    return render(request, 'user_list.html', context)


def user_detail(request, user_id):
    user_obj = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    profile = getattr(user_obj, 'profile', None)

    matches = Match.objects.filter(Q(user1=user_obj) | Q(user2=user_obj)).select_related('user1', 'user2').order_by('-matched_at')
    matched_pairs = [
        {
            'user': match.user1 if match.user2 == user_obj else match.user2,
            'matched_at': match.matched_at,
        }
        for match in matches
    ]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_block':
            user_obj.is_blocked = not user_obj.is_blocked
            user_obj.save(update_fields=['is_blocked'])
            messages.success(request, 'User blocked successfully.' if user_obj.is_blocked else 'User unblocked successfully.')
            return redirect('user_detail', user_id=user_id)

    return render(request, 'user_detail.html', {
        'user_obj': user_obj,
        'profile': profile,
        'matched_pairs': matched_pairs,
    })


def logout_view(request):
    logout(request)
    return redirect('admin_login')

def matches(request):
    all_matches = Match.objects.select_related('user1', 'user2').order_by('-matched_at')
    return render(request, 'matches.html', {'matches': all_matches})


def chat_background(request):
    if request.method == "POST":
        name = request.POST.get("name")
        image = request.FILES.get("image")

        if name and image:
            ChatBackground.objects.create(name=name, image=image)
            return redirect("chat_background")  # your URL name

    backgrounds = ChatBackground.objects.all()
    return render(request, 'chat_background.html', {"backgrounds": backgrounds})


@require_http_methods(["GET", "POST"])
def delete_account_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password")
            return redirect("delete_account")

        # Ensure logged-in user is deleting their own account
        if request.user.is_authenticated and request.user != user:
            messages.error(request, "You can only delete your own account")
            return redirect("delete_account")

        # Logout & delete
        logout(request)
        user.delete()

        messages.success(request, "Your account has been deleted successfully")
        return redirect("login")  # or homepage

    return render(request, "delete_account.html")

def privacy(request):
    return render(request, 'privacy.html')

def terms(request):
    return render(request, 'terms.html')

def child_safety(request):
    return render(request, 'child-safety.html')
