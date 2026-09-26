from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tutors.app.views import ReviewViewSet, StudentViewSet, TutorViewSet

router = DefaultRouter()
router.register("students", StudentViewSet)
router.register("tutors", TutorViewSet)
router.register("reviews", ReviewViewSet)

urlpatterns = [path("app/", include(router.urls))]
