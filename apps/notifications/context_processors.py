from .models import Notification


def notifications_nav(request):
    if not request.user.is_authenticated:
        return {'nav_unread_notifications_count': 0}
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return {'nav_unread_notifications_count': unread_count}

