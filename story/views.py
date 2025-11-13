from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from rest_framework.pagination import LimitOffsetPagination
from datetime import timedelta
from .models import StoryView, StoryModel
from .serializers import StorySerializer
from dating_backend.timezone_utils import format_to_ist
from swipe_feature.models import Match
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404


class UploadStoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = StorySerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            story = serializer.save(
                user=user,
                expires_at=timezone.now() + timedelta(hours=24)
            )

            # ✅ Serialize and include IST formatted times
            serialized_data = StorySerializer(story, context={'request': request}).data

            response_data = {
                "status": "200",
                "message": "Story uploaded successfully",
                "Response": [serialized_data]
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        # ❌ If validation fails
        return Response({
            "status": "400",
            "message": "Failed to upload story",
            "Response": [serializer.errors]
        }, status=status.HTTP_400_BAD_REQUEST)



class FetchStoriesAPIView(APIView, LimitOffsetPagination):
    """
    Fetch logged-in user's stories (as 'your_stories') and matched users' stories (as 'matched_user_stories'),
    both non-expired, with pagination and 'is_viewed' for others.
    """
    permission_classes = [IsAuthenticated]
    default_limit = 10  # default pagination limit

    def get(self, request):
        user = request.user
        now = timezone.now()

        # ✅ Fetch matched users
        matched_users_qs = Match.objects.filter(Q(user1=user) | Q(user2=user))
        matched_user_ids = [
            match.user1.id if match.user2 == user else match.user2.id
            for match in matched_users_qs
        ]

        # ✅ Logged-in user's active stories
        user_stories_qs = StoryModel.objects.filter(
            user=user, expires_at__gt=now
        ).select_related("user").order_by("-created_at")

        # ✅ Matched users' active stories
        matched_stories_qs = StoryModel.objects.filter(
            user__id__in=matched_user_ids, expires_at__gt=now
        ).select_related("user").order_by("-created_at")

        # ✅ Combine both for pagination
        all_stories_qs = user_stories_qs.union(matched_stories_qs).order_by("-created_at")
        paginated_stories = self.paginate_queryset(all_stories_qs, request, view=self)

        # ✅ Serialize
        serializer = StorySerializer(paginated_stories, many=True, context={'request': request})
        stories_data = serializer.data

        # ✅ Optimize view check (1 query instead of N)
        viewed_story_ids = set(
            StoryView.objects.filter(user=user, story__in=paginated_stories)
            .values_list("story_id", flat=True)
        )

        # ✅ Separate into 'your_stories' and 'matched_user_stories'
        your_stories = []
        matched_stories = []

        for story_data, story_obj in zip(stories_data, paginated_stories):
            if story_obj.user == user:
                your_stories.append(story_data)
            else:
                story_data["is_viewed"] = story_obj.id in viewed_story_ids
                matched_stories.append(story_data)

        # ✅ Final structured response
        return self.get_paginated_response({
            "status": "200",
            "message": "Stories fetched successfully",
            "Response": {
                "your_stories": your_stories,
                "matched_user_stories": matched_stories
            }
        })
    
class MarkStoryViewedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, story_id):
        """
        Mark a story as viewed by the logged-in user.
        """
        user = request.user
        story = get_object_or_404(StoryModel, id=story_id)

        # ✅ Prevent duplicate views
        view, created = StoryView.objects.get_or_create(story=story, user=user)

        if created:
            message = "Story marked as viewed successfully."
        else:
            message = "Story was already viewed."

        # ✅ Prepare response data
        viewer_data = {
            "id": user.id,
            "full_name": user.full_name,
            "profile_image": (
                request.build_absolute_uri(user.profile_photo.url)
                if user.profile_photo else None
            )
        }

        response_data = {
            "status": "200",
            "message": message,
            "Response": [{
                "story_id": story.id,
                "viewer": viewer_data
            }]
        }

        return Response(response_data, status=status.HTTP_200_OK)

    

class DeleteStoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, story_id):
        """
        Delete a story if it belongs to the logged-in user.
        """
        user = request.user
        story = get_object_or_404(StoryModel, id=story_id)

        # ❌ Ensure only the owner can delete the story
        if story.user != user:
            return Response({
                "status": "403",
                "message": "You are not allowed to delete this story.",
                "Response": []
            }, status=status.HTTP_403_FORBIDDEN)

        # ✅ Delete story
        story.delete()

        response_data = {
            "status": "200",
            "message": "Story deleted successfully",
            "Response": [{
                "story_id": story_id,
            }]
        }

        return Response(response_data, status=status.HTTP_200_OK)
