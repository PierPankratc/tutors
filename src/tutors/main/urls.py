from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tutors.app.urls")),
    # path("", RedirectView.as_view(url="/app/students/")),
    path("auth", include("rest_framework.urls")),
]
