from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Question(models.Model):
    """
    Represents a question posted by a user.
    """
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='questions_posted'
    )
    text = models.TextField()
    is_public = models.BooleanField(default=True)  # Can be toggled for visibility
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question by {self.author}: {self.text[:50]}"


class Answer(models.Model):
    """
    Represents an answer to a question, which can be anonymous or public.
    """
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='answers'
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='answers_given'
    )
    text = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_display_name(self):
        return "Anonymous" if self.is_anonymous else self.author.username

    def __str__(self):
        return f"Answer to '{self.question.text[:30]}' by {self.get_display_name()}"


class QuestionLike(models.Model):
    """
    Optional – for engagement tracking.
    Users can like interesting questions.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')


class AnswerLike(models.Model):
    """
    Optional – for engagement tracking on answers.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'answer')
