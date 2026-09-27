from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tutors.app.views import ReviewViewSet, StudentViewSet, TutorViewSet

router = DefaultRouter()
router.register("students", StudentViewSet, basename="students")
router.register("tutors", TutorViewSet, basename="tutors")
router.register("reviews", ReviewViewSet, "reviews")

urlpatterns = [path("app/", include(router.urls))]
