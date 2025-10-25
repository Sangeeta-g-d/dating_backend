from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Question
from .serializers import *
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class AddQuestionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QuestionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.save()
            
            # Serialize the question
            serialized_data = QuestionSerializer(question, context={'request': request}).data
            
            # Broadcast via channels
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "questions_group",
                {
                    "type": "send_new_question",
                    "question": serialized_data,
                }
            )

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
        

# add answer
class AddAnswerAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AnswerCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            answer = serializer.save()

            # Broadcast to connected clients viewing this question
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"askme_{answer.question.id}",
                {
                    "type": "send_new_answer",
                    "data": {
                        "status": "200",
                        "message": "New answer added",
                        "Response": [AnswerSerializer(answer, context={'request': request}).data]
                    }
                }
            )

            response_data = {
                "status": "200",
                "message": "Answer posted successfully",
                "Response": [AnswerSerializer(answer, context={'request': request}).data]
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            response_data = {
                "status": "400",
                "message": "Failed to post answer",
                "Response": [serializer.errors] if serializer.errors else []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)