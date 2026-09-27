from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from tutors.app.models import Review, Student, Tutor
from tutors.app.serializers import ReviewSerializer, StudentSerializer, TutorSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]
    # Написать разные разрешения под функции


class TutorViewSet(viewsets.ModelViewSet):
    queryset = Tutor.objects.all()
    serializer_class = TutorSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]

    # Написать разные разрешения под функции


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]
