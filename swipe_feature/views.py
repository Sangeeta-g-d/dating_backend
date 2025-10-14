from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Swipe, MatchRequest, Match
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
            return Response({
                "status": 400,
                "message": "User profile not found.",
                "response": []
            }, status=400)

        user_interests = user_profile.interests.all()

        # Filter users based on shared interests (excluding self)
        if user_interests.exists():
            matched_users = User.objects.filter(
                profile__interests__in=user_interests
            ).exclude(id=user.id).distinct()
        else:
            # If no interests, pick random users
            all_other_users = User.objects.exclude(id=user.id)
            matched_users = sample(list(all_other_users), min(len(all_other_users), 10))  # limit 10 random users

        response_data = []

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

            response_data.append({
                "id": matched_user.id,
                "full_name": matched_user.full_name,
                "profile_photo": profile_photo_url,
                "gender": profile.gender,
                "occupation": profile.occupation,
                "bio": profile.bio,
                "age": age,
                "interests": [i.name for i in profile.interests.all()],
            })

        return Response({
            "status": 200,
            "message": "Users fetched successfully",
            "response": response_data
        })


# swipe API
class SwipeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_user_id = request.data.get("to_user_id")
        is_liked = request.data.get("is_liked", False)

        if not to_user_id:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "message": "to_user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Create or update Swipe
        swipe, created = Swipe.objects.update_or_create(
            from_user=request.user,
            to_user=to_user,
            defaults={"is_liked": is_liked}
        )

        # If liked, create a match request
        if is_liked:
            # Check if the other user also liked you
            if Swipe.objects.filter(from_user=to_user, to_user=request.user, is_liked=True).exists():
                # Create match request if not exists
                match_request, _ = MatchRequest.objects.get_or_create(from_user=request.user, to_user=to_user)
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "You liked the user. Match request sent.",
                    "swipe": SwipeSerializer(swipe).data
                })
            else:
                return Response({
                    "status": status.HTTP_200_OK,
                    "message": "You liked the user.",
                    "swipe": SwipeSerializer(swipe).data
                })

        return Response({
            "status": status.HTTP_200_OK,
            "message": "You disliked the user.",
            "swipe": SwipeSerializer(swipe).data
        })


# Accept/Reject Match Request API
class MatchRequestActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        action = request.data.get("action")  # "accept" or "reject"

        try:
            match_request = MatchRequest.objects.get(id=request_id, to_user=request.user)
        except MatchRequest.DoesNotExist:
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "Match request not found"}, status=status.HTTP_404_NOT_FOUND)

        if action == "accept":
            match_request.accept()
            return Response({"status": status.HTTP_200_OK, "message": "Match request accepted"})
        elif action == "reject":
            match_request.is_rejected = True
            match_request.responded_at = timezone.now()
            match_request.save()
            return Response({"status": status.HTTP_200_OK, "message": "Match request rejected"})
        else:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)


# matched list
class MatchesListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        matches1 = Match.objects.filter(user1=request.user)
        matches2 = Match.objects.filter(user2=request.user)
        matches = matches1.union(matches2)
        serializer = MatchSerializer(matches, many=True)
        return Response({
            "status": status.HTTP_200_OK,
            "message": "Matches retrieved successfully",
            "response": serializer.data
        })
