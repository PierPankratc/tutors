from rest_framework import serializers

from .models import Review, Student, Tutor


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "name", "email", "age", "created_at"]
        read_only_fields = ["id", "created_at"]


class TutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tutor
        fields = [
            "id",
            "name",
            "last_name",
            "is_high_edu",
            "experience",
            "rating",
            "count_review",
            "email",
            "age",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "creator", "tutor", "rating", "text", "created_at"]
        read_only_fields = ["id", "created_at"]
