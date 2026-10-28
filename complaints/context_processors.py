def navigation(request):
    if not request.user.is_authenticated:
        return {}

    notifications = request.user.notifications.select_related("complaint")[:6]
    unread_count = request.user.notifications.filter(is_read=False).count()
    return {
        "nav_notifications": notifications,
        "unread_count": unread_count,
    }
