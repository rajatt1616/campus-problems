from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Complaint, Notification, Remark, StatusEvent, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("name", "email", "role", "department", "is_active")
    list_filter = ("role", "department", "is_active")
    search_fields = ("name", "email", "department")
    ordering = ("name",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Campus profile",
            {"fields": ("name", "role", "department")},
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Campus profile",
            {"fields": ("name", "email", "role", "department")},
        ),
    )


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "category",
        "priority",
        "status",
        "created_by",
        "assigned_to",
        "updated_at",
    )
    list_filter = ("status", "category", "priority")
    search_fields = ("number", "title", "description")
    readonly_fields = ("number", "created_at", "updated_at", "closed_at")
    date_hierarchy = "created_at"


@admin.register(Remark)
class RemarkAdmin(admin.ModelAdmin):
    list_display = ("complaint", "author_name", "author_role", "created_at")
    search_fields = ("text", "author_name", "complaint__number")


@admin.register(StatusEvent)
class StatusEventAdmin(admin.ModelAdmin):
    list_display = (
        "complaint",
        "from_status",
        "to_status",
        "actor_name",
        "created_at",
    )
    list_filter = ("from_status", "to_status")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("message", "user__email")
