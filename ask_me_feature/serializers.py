from rest_framework import serializers
from .models import Question,Answer
from dating_backend.timezone_utils import format_to_ist

class QuestionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'is_public', 'created_at', 'author_name']


class QuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['text', 'is_public']

    def create(self, validated_data):
        user = self.context['request'].user
        question = Question.objects.create(author=user, **validated_data)
        return question


class AnswerSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ['id', 'question', 'text', 'is_anonymous', 'created_at', 'author_name']

    def get_author_name(self, obj):
        return "Anonymous" if obj.is_anonymous else obj.author.full_name


class AnswerCreateSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Answer
        fields = ['question_id', 'text', 'is_anonymous']

    def validate_question_id(self, value):
        if not Question.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid question ID.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        question = Question.objects.get(id=validated_data.pop('question_id'))
        answer = Answer.objects.create(author=user, question=question, **validated_data)
        return answer


class MyQuestionSerializer(serializers.ModelSerializer):
    answers_count = serializers.IntegerField(source='answers.count', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'text',
            'is_public',
            'created_at',
            'answers_count',
            'likes_count'
        ]

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)