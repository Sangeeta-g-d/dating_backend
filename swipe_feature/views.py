from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Swipe, Match
from django.contrib.auth import get_user_model
from .serializers import *
from django.utils import timezone
from random import sample
from django.db.models import Q
User = get_user_model()
from notifications.utils import create_notification
# Create your views here.



# user list
class SwipeUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_profile = getattr(user, "profile", None)

        if not user_profile:
            response_data = {
                "status": "400",
                "message": "User profile not found.",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        # Get user's preferences
        meet_preference = user_profile.would_like_to_meet
        user_interests = user_profile.interests.all()

        # Filter base users (exclude self)
        already_swiped_ids = Swipe.objects.filter(from_user=user).values_list('to_user_id', flat=True)
        users_qs = User.objects.exclude(id__in=already_swiped_ids).exclude(id=user.id)

        # --- GENDER FILTER ---
        if meet_preference != "everyone":
            users_qs = users_qs.filter(profile__gender=meet_preference)

        # --- INTEREST FILTER ---
        if user_interests.exists():
            matched_users = users_qs.filter(
                profile__interests__in=user_interests
            ).distinct()
        else:
            # If no interests, pick random users
            all_other_users = list(users_qs)
            matched_users = sample(all_other_users, min(len(all_other_users), 10))

        response_list = []

        for matched_user in matched_users:
            profile = getattr(matched_user, "profile", None)
            if not profile:
                continue

            # Calculate age
            age = None
            if profile.date_of_birth:
                today = timezone.now().date()
                age = today.year - profile.date_of_birth.year - (
                    (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
                )

            # Full URL for profile photo
            profile_photo_url = (
                request.build_absolute_uri(matched_user.profile_photo.url)
                if matched_user.profile_photo else None
            )

            response_list.append({
                "id": matched_user.id,
                "full_name": matched_user.full_name,
                "profile_photo": profile_photo_url,
                "gender": profile.gender,
                "occupation": profile.occupation,
                "bio": profile.bio,
                "age": age,
                "interests": [i.name for i in profile.interests.all()],
            })

        response_data = {
            "status": "200",
            "message": "Users fetched successfully",
            "Response": response_list if response_list else []
        }

        return Response(response_data, status=status.HTTP_200_OK)

# swipe API
from django.utils.timezone import now, timedelta

class SwipeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        to_user_id = request.data.get("to_user_id")
        is_liked_raw = request.data.get("is_liked", False)

        # Convert to boolean safely
        is_liked = str(is_liked_raw).lower() in ["true", "1", "yes"]

        if not to_user_id:
            return Response({
                "status": "400",
                "message": "to_user_id is required",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({
                "status": "404",
                "message": "User not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)


        # -----------------------------------------------------------
        # 🔥 DAILY SWIPE LIMIT CHECK
        # -----------------------------------------------------------
        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)

        today_swipes = Swipe.objects.filter(
            from_user=user,
            created_at__gte=today_start
        ).count()

        # Check if user has a subscription
        user_sub = getattr(user, "subscription", None)

        if user_sub and user_sub.is_active:
            # If plan has swipe limit, apply it (Else unlimited)
            plan_limit = user_sub.plan.swipe_limit

            if plan_limit is not None and today_swipes >= plan_limit:
                return Response({
                    "status": "403",
                    "message": "Daily swipe limit reached for your subscription plan",
                    "Response": []
                }, status=403)

        else:
            # ❗ Non-subscription users → only 10 daily swipes
            if today_swipes >= 10:
                return Response({
                    "status": "403",
                    "message": "Free daily swipe limit reached (10 swipes per day)",
                    "Response": []
                }, status=403)


        # -----------------------------------------------------------
        # Prevent duplicate swipe
        # -----------------------------------------------------------
        if Swipe.objects.filter(from_user=user, to_user=to_user).exists():
            return Response({
                "status": "400",
                "message": "You have already swiped on this user.",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)


        # Create swipe entry
        swipe = Swipe.objects.create(
            from_user=user,
            to_user=to_user,
            is_liked=is_liked
        )

        swipe_data = SwipeSerializer(swipe).data


        # -----------------------------------------------------------
        # LIKE / DISLIKE HANDLING
        # -----------------------------------------------------------
        if is_liked:
            if Swipe.objects.filter(from_user=to_user, to_user=user, is_liked=True).exists():
                message = "It's a match!"
                swipe.accept()
            else:
                message = "You liked the user."
        else:
            swipe.reject()
            message = "You disliked the user."


        return Response({
            "status": "200",
            "message": message,
            "Response": [swipe_data]
        })



# received match requests
class ReceivedMatchRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            # Ensure user profile exists
            user_profile = getattr(user, "profile", None)
            if not user_profile:
                response_data = {
                    "status": "400",
                    "message": "User profile not found.",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # Fetch all pending requests (liked but not accepted/rejected)
            received_swipes = Swipe.objects.filter(
                to_user=user,
                is_liked=True,
                is_accepted=False,
                is_rejected=False
            ).select_related("from_user", "from_user__profile")

            if not received_swipes.exists():
                response_data = {
                    "status": "404",
                    "message": "No pending match requests.",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            response_list = []

            for swipe in received_swipes:
                from_user = swipe.from_user
                profile = getattr(from_user, "profile", None)
                if not profile:
                    continue  # skip users without profile

                # Calculate age if available
                age = None
                if profile.date_of_birth:
                    today = timezone.now().date()
                    age = today.year - profile.date_of_birth.year - (
                        (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
                    )

                # Profile photo URL
                profile_photo_url = (
                    request.build_absolute_uri(from_user.profile_photo.url)
                    if from_user.profile_photo else None
                )

                response_list.append({
                    "request_id": swipe.id,
                    "user_id": from_user.id,
                    "full_name": from_user.full_name,
                    "profile_photo": profile_photo_url,
                    "occupation": profile.occupation,
                    "age": age,
                    "created_at": swipe.created_at,
                })

            response_data = {
                "status": "200",
                "message": "Pending match requests fetched successfully.",
                "Response": response_list if response_list else []
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            response_data = {
                "status": "500",
                "message": f"An unexpected error occurred: {str(e)}",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Accept/Reject Match Request API
class SwipeActionAPIView(APIView):
    """
    API to accept or reject a swipe request.
    A swipe can only be accepted/rejected by the `to_user`.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, swipe_id):
        action = request.data.get("action")  # "accept" or "reject"

        if action not in ["accept", "reject"]:
            return Response({
                "status": "400",
                "message": "Invalid action. Allowed actions are 'accept' or 'reject'.",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            swipe = Swipe.objects.get(id=swipe_id, to_user=request.user, is_liked=True)
        except Swipe.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Swipe not found or unauthorized.",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        # ------------ ACCEPT ------------
        if action == "accept":
            swipe.accept()

            # 🔔 Create notification for the user who swiped (from_user)
            create_notification(
                receiver=swipe.from_user,
                sender=request.user,
                notif_type="new_match",
                message=f"{request.user.full_name} accepted your match request!",
                extra_data={
                    "swipe_id": swipe.id,
                    "from_user_id": swipe.from_user.id,
                    "to_user_id": swipe.to_user.id
                }
            )

            return Response({
                "status": "200",
                "message": "Match request accepted successfully.",
                "Response": [
                    {
                        "swipe_id": swipe.id,
                        "from_user_id": swipe.from_user.id,
                        "to_user_id": swipe.to_user.id,
                        "action": "accepted",
                        "updated_at": swipe.updated_at if hasattr(swipe, "updated_at") else None
                    }
                ]
            }, status=status.HTTP_200_OK)

        # ------------ REJECT ------------
        elif action == "reject":
            swipe.reject()

            return Response({
                "status": "200",
                "message": "Match request rejected successfully.",
                "Response": [
                    {
                        "swipe_id": swipe.id,
                        "from_user_id": swipe.from_user.id,
                        "to_user_id": swipe.to_user.id,
                        "action": "rejected",
                        "updated_at": swipe.updated_at if hasattr(swipe, "updated_at") else None
                    }
                ]
            }, status=status.HTTP_200_OK)
        

class MatchedUsersListAPIView(APIView):
    """
    Returns all users who have mutually accepted matches with the logged-in user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            matched_users = Match.get_user_matches(user)

            # If no matches found
            if not matched_users:
                response_data = {
                    "status": "404",
                    "message": "No matches found.",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            response_list = []

            for matched_user in matched_users:
                profile = getattr(matched_user, "profile", None)

                # Profile photo URL
                profile_photo_url = (
                    request.build_absolute_uri(matched_user.profile_photo.url)
                    if matched_user.profile_photo else None
                )

                response_list.append({
                    "user_id": matched_user.id,
                    "full_name": matched_user.full_name,
                    "profile_photo": profile_photo_url,
                    "is_online": profile.is_online if profile else False,
                })

            response_data = {
                "status": "200",
                "message": "Matched users fetched successfully.",
                "Response": response_list if response_list else []
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            response_data = {
                "status": "500",
                "message": f"An unexpected error occurred: {str(e)}",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UnmatchAPIView(APIView):
    """
    Unmatch a user with whom the logged-in user has a mutual match.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, matched_user_id):
        try:
            user = request.user

            # Check if match exists between user and matched_user_id
            match = Match.objects.filter(
                Q(user1_id=user.id, user2_id=matched_user_id) |
                Q(user1_id=matched_user_id, user2_id=user.id)
            ).first()

            if not match:
                return Response(
                    {
                        "status": "404",
                        "message": "Match not found.",
                        "Response": {}
                        },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Delete match
            match.delete()

            # OPTIONAL: Clear related swipe data so they can swipe again later
            Swipe.objects.filter(
                Q(from_user=user, to_user_id=matched_user_id) |
                Q(from_user_id=matched_user_id, to_user=user)
            ).delete()

            return Response(
                {
                    "status": "200",
                    "message": "Successfully unmatched.",
                    "Response": {}
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "status": "500",
                    "message": f"Unexpected error: {str(e)}",
                    "Response": {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )