from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tutors.app.urls")),
    path("auth/", include("rest_framework.urls")),
]

