from rest_framework import serializers

from .models import Review, Student, Tutor


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "name", "email", "age", "created_at"]


class TutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tutor
        fields = [
            "id",
            "name",
            "last_name",
            "is_high_edu",
            "experience",
            "email",
            "age",
            "created_at",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "author", "rating", "text", "created_at"]
