from django.urls import path
from .views import *

urlpatterns = [
    path('ask-question/', AddQuestionAPIView.as_view(), name='ask-question'),
    path('answer-question/<int:question_id>/', AddAnswerAPIView.as_view(),name='answer-question'),
    path('questions/',QuestionListAPIView.as_view(),name="questions"),
    path('view-all-ans/<int:question_id>/',QuestionAnswersAPIView.as_view(),name="view-all-ans")

]