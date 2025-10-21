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

User = get_user_model()
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
        users_qs = User.objects.exclude(id=user.id)

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
class SwipeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_user_id = request.data.get("to_user_id")
        is_liked = request.data.get("is_liked", False)

        if not to_user_id:
            response_data = {
                "status": "400",
                "message": "to_user_id is required",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            response_data = {
                "status": "404",
                "message": "User not found",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        # Create or update Swipe
        swipe, created = Swipe.objects.update_or_create(
            from_user=request.user,
            to_user=to_user,
            defaults={"is_liked": is_liked}
        )

        swipe_data = SwipeSerializer(swipe).data

        # Determine message
        if is_liked:
            # Check if the other user also liked you
            if Swipe.objects.filter(from_user=to_user, to_user=request.user, is_liked=True).exists():
                message = "You liked the user. Match request sent."
            else:
                message = "You liked the user."
        else:
            message = "You disliked the user."

        response_data = {
            "status": "200",
            "message": message,
            "Response": [swipe_data] if swipe_data else []
        }

        return Response(response_data, status=status.HTTP_200_OK)

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

        # Validate action
        if action not in ["accept", "reject"]:
            response_data = {
                "status": "400",
                "message": "Invalid action. Allowed actions are 'accept' or 'reject'.",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        try:
            swipe = Swipe.objects.get(id=swipe_id, to_user=request.user, is_liked=True)
        except Swipe.DoesNotExist:
            response_data = {
                "status": "404",
                "message": "Swipe not found or unauthorized.",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        # Perform the action
        if action == "accept":
            swipe.accept()
            response_data = {
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
            }
            return Response(response_data, status=status.HTTP_200_OK)

        elif action == "reject":
            swipe.reject()
            response_data = {
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
            }
            return Response(response_data, status=status.HTTP_200_OK)

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
