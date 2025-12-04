from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .serializers import *
from rest_framework.pagination import PageNumberPagination
from swipe_feature.models import Match
from auth_api.models import CustomUser
from .models import Post, Like
from django.shortcuts import get_object_or_404
from notifications.helper import handle_profile_view
from notifications.utils import create_notification


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

        # Include logged-in user's own posts as well
        all_users = list(matched_users) + [user]

        # Fetch posts of matched users + logged-in user, newest first
        posts = Post.objects.filter(user__in=all_users).order_by('-created_at')

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 10  # adjust as needed
        paginated_posts = paginator.paginate_queryset(posts, request)

        serializer = PostSerializer(paginated_posts, many=True, context={"request": request, "current_user": user})

        response_data = {
            "status": "200",
            "message": "Matched user posts (including your posts) fetched successfully",
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

        # ⭐ Trigger profile-view event here
        handle_profile_view(request.user, other_user)

        # Check match status
        is_matched = other_user in Match.get_user_matches(request.user)

        # Get profile instance
        profile = getattr(other_user, "profile", None)
        if not profile:
            return Response({
                "status": "404",
                "message": "User profile not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        # Serialize profile
        profile_serializer = UserProfileSerializer(profile)

        # Get posts and post count (irrespective of match)
        posts = Post.objects.filter(user=other_user).order_by('-created_at')
        post_count = posts.count()

        # Only include post details if matched
        if is_matched:
            posts_serializer = UserPostSerializer(posts, many=True)
            posts_data = posts_serializer.data
            message = "User profile (matched) fetched successfully"
        else:
            posts_data = []
            message = "User profile fetched successfully (not matched)"

        # Final response
        response_data = {
            "status": "200",
            "message": message,
            "Response": {
                "isMatched": is_matched,
                "post_count": post_count,
                "profile": profile_serializer.data,
                "posts": posts_data
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
            # Already liked → unlike
            like.delete()
            is_liked = False
            message = "Post unliked successfully"
        else:
            is_liked = True
            message = "Post liked successfully"

            # 🔔 CREATE NOTIFICATION
            create_notification(
                receiver=post.user, 
                sender=user,
                notif_type="like",
                message=f"{user.full_name} liked your post.",
                extra_data={"post_id": post.id}
            )

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

        # 🔔 Notify post owner (only if commenter is not the owner)
        create_notification(
            receiver=post.user,
            sender=request.user,
            notif_type="comment",
            message=f"{request.user.full_name} commented on your post.",
            extra_data={"post_id": post.id, "comment_id": comment.id}
        )

        response_data = {
            "status": "200",
            "message": "Comment added successfully",
            "Response": {
                "comment_id": comment.id,
                "post_id": post.id,
                "user": request.user.full_name if hasattr(request.user, 'full_name') else request.user.full_name,
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

        # Only post owner can reply
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

        # 🔔 Notify original commenter (if not replying to own comment)
        create_notification(
            receiver=parent_comment.user,
            sender=request.user,
            notif_type="comment",
            message=f"{request.user.full_name} replied to your comment.",
            extra_data={
                "post_id": post.id,
                "comment_id": parent_comment.id,
                "reply_id": reply.id
            }
        )

        response_data = {
            "status": "200",
            "message": "Reply added successfully",
            "Response": {
                "reply_id": reply.id,
                "post_id": post.id,
                "parent_comment_id": parent_comment.id,
                "user": request.user.full_name if hasattr(request.user, 'full_name') else request.user.full_name,
                "content": reply.content,
                "created_at": format_to_ist(reply.created_at),
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)


class PostDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, post_id):
        """
        Fetch a single post by ID including like count, comment count, and is_liked.
        """
        post = get_object_or_404(
            Post.objects.prefetch_related("likes", "comments", "user"),
            id=post_id
        )

        serializer = PostDetailSerializer(post, context={"request": request})

        return Response({
            "status": "200",
            "message": "Post fetched successfully",
            "Response": serializer.data
        })