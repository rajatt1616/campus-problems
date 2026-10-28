from django.contrib import admin
from django.urls import include, path

handler400 = "complaints.views.error_400"
handler403 = "complaints.views.error_403"
handler404 = "complaints.views.error_404"
handler500 = "complaints.views.error_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("complaints.urls")),
]
