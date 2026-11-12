from django.contrib import admin
from django.urls import include, path

from core.views import healthz

admin.site.site_header = "TeamBase admin"

urlpatterns = [
    path("api/", include("core.urls")),
    path("admin/", admin.site.urls),
    path("healthz", healthz),
]
# Everything else is the exported Next.js frontend, served from FRONTEND_DIR by WhiteNoise.
