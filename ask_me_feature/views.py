from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Question
from .serializers import *
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from dating_backend.timezone_utils import format_to_ist
from django.db.models import Prefetch
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404


class AddQuestionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QuestionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.save()

            # Serialize the question
            serialized_data = QuestionSerializer(question, context={'request': request}).data

            # ✅ Format created_at (or any datetime field) to IST
            if 'created_at' in serialized_data:
                serialized_data['created_at'] = format_to_ist(question.created_at)

            if 'updated_at' in serialized_data:
                serialized_data['updated_at'] = format_to_ist(question.updated_at)

            # ✅ Broadcast via channels
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     "questions_group",
            #     {
            #         "type": "send_new_question",
            #         "question": serialized_data,
            #     }
            # )

            response_data = {
                "status": "200",
                "message": "Question posted successfully",
                "Response": [serialized_data]
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        else:
            response_data = {
                "status": "400",
                "message": "Failed to post question",
                "Response": [serializer.errors] if serializer.errors else []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        

class AddAnswerAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, question_id):
        # ✅ Check if question exists
        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Question not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        # ✅ Attach question_id automatically
        data = request.data.copy()
        data["question_id"] = question_id

        serializer = AnswerCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            answer = serializer.save()

            # ✅ Serialize with IST time formatting
            serialized_data = AnswerSerializer(answer, context={'request': request}).data
            serialized_data["created_at"] = format_to_ist(answer.created_at)

            response_data = {
                "status": "200",
                "message": "Answer posted successfully",
                "Response": [serialized_data]
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        return Response({
            "status": "400",
            "message": "Failed to post answer",
            "Response": [serializer.errors]
        }, status=status.HTTP_400_BAD_REQUEST)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  # default items per page
    page_size_query_param = 'page_size'
    max_page_size = 100


# ✅ Main API view
class QuestionListAPIView(APIView):
    """
    Fetch all public questions except those posted by the logged-in user,
    ordered by latest, and include up to 3 latest answers per question.
    Includes pagination and full image URLs.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ Base queryset
        questions = (
            Question.objects.filter(is_public=True)
            .exclude(author=user)
            .order_by("-created_at")
            .prefetch_related(
                Prefetch(
                    "answers",
                    queryset=Answer.objects.order_by("-created_at")[:3],
                    to_attr="latest_answers",
                )
            )
        )

        # ✅ Apply pagination
        paginator = StandardResultsSetPagination()
        paginated_questions = paginator.paginate_queryset(questions, request)

        # ✅ Serialize manually with IST formatting & profile images
        data = []
        for q in paginated_questions:
            author_profile_image = (
                request.build_absolute_uri(q.author.profile_photo.url)
                if q.author.profile_photo
                else None
            )

            question_data = {
                "id": q.id,
                "text": q.text,
                "author": q.author.full_name or q.author.email,
                "author_profile_image": author_profile_image,
                "created_at": format_to_ist(q.created_at),
                "answers": [],
            }

            for ans in getattr(q, "latest_answers", []):
                if ans.is_anonymous:
                    ans_author_name = "Anonymous"
                    ans_author_image = None
                else:
                    ans_author_name = ans.author.full_name or ans.author.email
                    ans_author_image = (
                        request.build_absolute_uri(ans.author.profile_photo.url)
                        if ans.author.profile_photo
                        else None
                    )

                question_data["answers"].append({
                    "id": ans.id,
                    "text": ans.text,
                    "author": ans_author_name,
                    "author_profile_image": ans_author_image,
                    "is_anonymous": ans.is_anonymous,
                    "created_at": format_to_ist(ans.created_at),
                })

            data.append(question_data)

        # ✅ Paginated response
        return paginator.get_paginated_response({
            "status": "200",
            "message": "Questions fetched successfully",
            "Response": data
        })
    

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class QuestionAnswersAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, question_id):
        """
        Get all answers for a given question (ordered by latest)
        """
        question = get_object_or_404(Question, id=question_id)

        answers = Answer.objects.filter(question=question).order_by('-created_at')

        paginator = StandardResultsPagination()
        paginated_answers = paginator.paginate_queryset(answers, request)

        serializer = AnswerSerializer(paginated_answers, many=True, context={'request': request})

        response_data = {
            "status": "200",
            "message": f"Answers fetched successfully for question ID {question_id}",
            "Response": serializer.data,
        }

        return paginator.get_paginated_response(response_data)


class MyQuestionsListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Returns all questions posted by logged-in user
        """
        user = request.user
        questions = Question.objects.filter(author=user).order_by('-created_at')

        serializer = MyQuestionSerializer(questions, many=True, context={'request': request})

        return Response({
            "status": "200",
            "message": "User questions fetched successfully",
            "Response": serializer.data
        })