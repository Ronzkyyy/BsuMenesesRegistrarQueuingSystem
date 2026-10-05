"""
Celery worker for background tasks
Handles queue processing, notifications, reminders
"""
from celery import Celery
from app.core.config import settings
from app.core.redis_ssl import configure_redis_ssl

celery = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.notifications"]
)
configure_redis_ssl(celery, settings.REDIS_URL)

celery.conf.task_routes = {
    "app.services.notifications.*": {"queue": "notifications"},
}

# Configure Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Manila",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Beat schedule for periodic tasks
celery.conf.beat_schedule = {
    "update-wait-times-every-minute": {
        "task": "app.services.notifications.update_all_wait_times",
        "schedule": 60.0,
    },
    "check-no-show-tickets-every-5-minutes": {
        "task": "app.services.notifications.check_no_show_tickets",
        "schedule": 300.0,
    },
    # send_reminder_check is paused: there's no SMS/email channel yet, so it
    # only re-logged the next few tickets every 5 minutes. Re-add it here once
    # send_ticket_reminder actually delivers something.
    "expire-stale-appointments-every-5-minutes": {
        "task": "app.services.notifications.expire_stale_appointments",
        "schedule": 300.0,
    },
}


@celery.task
def send_ticket_reminder(ticket_id: int):
    """Send reminder to student about their queue position"""
    from app.services.notifications import send_ticket_reminder as notify
    return notify.delay(ticket_id)


@celery.task
def send_ticket_called(ticket_id: int):
    """Notify student that their ticket is being called"""
    from app.services.notifications import send_ticket_called as notify
    return notify.delay(ticket_id)