from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .serializers import *
from rest_framework.pagination import PageNumberPagination
from swipe_feature.models import Match
from auth_api.models import CustomUser
from .models import Post, Like
from django.shortcuts import get_object_or_404

class AddPostAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PostCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            post = serializer.save()
            return Response({
                "status": "200",
                "message": "Post created successfully",
                "Response": PostSerializer(post, context={'request': request}).data  # ✅ fixed here
            }, status=status.HTTP_201_CREATED)
        return Response({
            "status": "400",
            "message": "Failed to create post",
            "Response": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class MatchedUserPostsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get all matched users
        matched_users = Match.get_user_matches(user)

        # Fetch posts of matched users, newest first
        posts = Post.objects.filter(user__in=matched_users).order_by('-created_at')

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 10  # adjust page size
        paginated_posts = paginator.paginate_queryset(posts, request)

        serializer = PostSerializer(paginated_posts, many=True, context={"request": request})

        response_data = {
            "status": "200",
            "message": "Matched user posts fetched successfully",
            "Response": serializer.data if serializer.data else []
        }

        return paginator.get_paginated_response(response_data)
    
class PostCommentsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({
                "status": 404,
                "message": "Post not found"
            }, status=status.HTTP_404_NOT_FOUND)

        comments = post.comments.filter(parent__isnull=True).order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 10  # optional pagination
        paginated_comments = paginator.paginate_queryset(comments, request)

        serializer = CommentSerializer(paginated_comments, many=True, context={"request": request})

        response_data = {
            "status": 200,
            "message": "Comments fetched successfully",
            "Response": serializer.data
        }

        return paginator.get_paginated_response(response_data)


class UserProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        try:
            other_user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({
                "status": "404",
                "message": "User not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if logged-in user is matched with this user
        is_matched = other_user in Match.get_user_matches(request.user)

        # -------------------------------
        # Case 1: Not Matched — show limited info
        # -------------------------------
        if not is_matched:
            response_data = {
                "status": "200",
                "message": "User profile limited due to no match",
                "Response": {
                    "user_name": other_user.full_name,
                    "profile_photo": other_user.profile_photo.url if other_user.profile_photo else None
                }
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # -------------------------------
        # Case 2: Matched — show full profile + posts
        # -------------------------------
        profile = getattr(other_user, "profile", None)
        if not profile:
            return Response({
                "status": "404",
                "message": "User profile not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        profile_serializer = UserProfileSerializer(profile)

        # Get all posts (no pagination)
        posts = Post.objects.filter(user=other_user).order_by('-created_at')
        posts_serializer = UserPostSerializer(posts, many=True)

        response_data = {
            "status": "200",
            "message": "User profile fetched successfully",
            "Response": {
                "profile": profile_serializer.data,
                "posts": posts_serializer.data if posts_serializer.data else []
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

# like API
class ToggleLikeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Post not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        like, created = Like.objects.get_or_create(user=user, post=post)

        if not created:
            # Already liked → unlike it
            like.delete()
            is_liked = False
            message = "Post unliked successfully"
        else:
            is_liked = True
            message = "Post liked successfully"

        response_data = {
            "status": "200",
            "message": message,
            "Response": {
                "post_id": post.id,
                "is_liked": is_liked,
                "total_likes": post.total_likes()
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
    

# add comment api
class AddCommentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Post not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get("content")

        if not content or content.strip() == "":
            return Response({
                "status": "400",
                "message": "Comment content is required",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = Comment.objects.create(
            user=request.user,
            post=post,
            content=content.strip()
        )

        response_data = {
            "status": "200",
            "message": "Comment added successfully",
            "Response": {
                "comment_id": comment.id,
                "post_id": post.id,
                "user": request.user.full_name if hasattr(request.user, 'full_name') else request.user.username,
                "content": comment.content,
                "created_at": format_to_ist(comment.created_at),
                "total_comments": post.total_comments(),
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
    

class ReplyToCommentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, comment_id):
        try:
            parent_comment = Comment.objects.select_related('post').get(id=comment_id)
        except Comment.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Comment not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        post = parent_comment.post

        # ✅ Allow only post owner to reply
        if post.user != request.user:
            return Response({
                "status": "403",
                "message": "Only the post owner can reply to comments",
                "Response": []
            }, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("content")
        if not content or content.strip() == "":
            return Response({
                "status": "400",
                "message": "Reply content is required",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        reply = Comment.objects.create(
            user=request.user,
            post=post,
            content=content.strip(),
            parent=parent_comment
        )

        response_data = {
            "status": "200",
            "message": "Reply added successfully",
            "Response": {
                "reply_id": reply.id,
                "post_id": post.id,
                "parent_comment_id": parent_comment.id,
                "user": request.user.full_name if hasattr(request.user, 'full_name') else request.user.username,
                "content": reply.content,
                "created_at": format_to_ist(reply.created_at),
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)