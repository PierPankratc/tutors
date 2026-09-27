from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.decorators import api_view
from rest_framework.response import Response

from tutors.app.filters import TutorFilter
from tutors.app.models import Review, Student, Tutor
from tutors.app.serializers import ReviewSerializer, StudentSerializer, TutorSerializer
from django.core.cache import cache

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
    filterset_class = TutorFilter

    # Написать разные разрешения под функции


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]

    def get_queryset(self):
        cache_key = 'tutors_list'
        queryset = cache.get(cache_key)
        if queryset is None:
            queryset = list(Tutor.objects.all())
            cache.set(key=cache_key, value=queryset, timeout=300)

        return queryset



@api_view(["GET"])
def most_popilar(request):
    tutors = Tutor.objects.order_by("-rating")[:10]
    serializer = TutorSerializer(tutors, many=True)
    return Response(serializer.data)

