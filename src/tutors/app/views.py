from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from tutors.app.filters import TutorFilter
from tutors.app.models import Review, Student, Tutor
from tutors.app.serializers import ReviewSerializer, StudentSerializer, TutorSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]


class TutorViewSet(viewsets.ModelViewSet):
    queryset = Tutor.objects.all()
    serializer_class = TutorSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]
    filterset_class = TutorFilter

    def list(self, request, *args, **kwargs):
        if not request.query_params:
            cache_key = "tutors_list"
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(cached_data)

            response = super().list(request, *args, **kwargs)
            cache.set(key=cache_key, value=response.data, timeout=300)
            return response

        return super().list(request, *args, **kwargs)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]


@api_view(["GET"])
def most_popilar(request):
    tutors = Tutor.objects.order_by("-rating")[:10]
    serializer = TutorSerializer(tutors, many=True)
    return Response(serializer.data)
