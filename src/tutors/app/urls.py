from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tutors.app.views import ReviewViewSet, StudentViewSet, TutorViewSet, most_popilar

router = DefaultRouter()
router.register("students", StudentViewSet, basename="students")
router.register("tutors", TutorViewSet, basename="tutors")
router.register("reviews", ReviewViewSet, basename="reviews")

urlpatterns = [
    path("app/", include(router.urls)),
    path("top/", most_popilar, name="most_popular"),
]
