from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.ComplaintLoginView.as_view(), name="login"),
    path("logout/", views.ComplaintLogoutView.as_view(), name="logout"),
    path("dashboard/student/", views.student_dashboard, name="dashboard_student"),
    path("dashboard/admin/", views.admin_dashboard, name="dashboard_admin"),
    path(
        "dashboard/department/",
        views.department_dashboard,
        name="dashboard_department",
    ),
    path("complaints/new/", views.complaint_create, name="complaint_create"),
    path(
        "complaints/<str:number>/",
        views.complaint_detail,
        name="complaint_detail",
    ),
    path(
        "complaints/<str:number>/edit/",
        views.complaint_edit,
        name="complaint_edit",
    ),
    path(
        "complaints/<str:number>/delete/",
        views.complaint_delete,
        name="complaint_delete",
    ),
    path(
        "complaints/<str:number>/assign/",
        views.assign_complaint,
        name="assign_complaint",
    ),
    path(
        "complaints/<str:number>/start/",
        views.start_complaint,
        name="start_complaint",
    ),
    path(
        "complaints/<str:number>/resolve/",
        views.resolve_complaint,
        name="resolve_complaint",
    ),
    path(
        "complaints/<str:number>/accept/",
        views.accept_complaint,
        name="accept_complaint",
    ),
    path(
        "complaints/<str:number>/reject/",
        views.reject_complaint,
        name="reject_complaint",
    ),
    path(
        "complaints/<str:number>/reopen/",
        views.reopen_complaint,
        name="reopen_complaint",
    ),
    path(
        "complaints/<str:number>/remarks/",
        views.add_remark,
        name="add_remark",
    ),
    path("search/", views.search, name="search"),
    path(
        "notifications/read/",
        views.mark_notifications_read,
        name="mark_notifications_read",
    ),
    path("api/stats/", views.api_stats, name="api_stats"),
    path("export/complaints.json", views.export_complaints, name="export_complaints"),
]
