"""
Notification service for Celery worker
Handles SMS, email, and WebSocket notifications for queue updates
"""
from celery import Celery
from app.core.config import settings
from app.core.database import SessionLocal
from app.db_models import TicketDB, TicketDBStatus, QueueDB, StudentDB
from app.services.ticket_service import TicketService
import logging

logger = logging.getLogger(__name__)

celery = Celery(
    "notifications",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.task_routes = {
    "app.services.notifications.*": {"queue": "notifications"},
}

celery.conf.beat_schedule = {
    "update-wait-times-every-minute": {
        "task": "app.services.notifications.update_all_wait_times",
        "schedule": 60.0,  # every minute
    },
    "check-no-show-tickets-every-5-minutes": {
        "task": "app.services.notifications.check_no_show_tickets",
        "schedule": 300.0,  # every 5 minutes
    },
    "expire-stale-appointments-every-5-minutes": {
        "task": "app.services.notifications.expire_stale_appointments",
        "schedule": 300.0,  # every 5 minutes
    },
}


@celery.task(bind=True, max_retries=3)
def send_ticket_reminder(self, ticket_id: int):
    """Send reminder to student about their queue position"""
    db = SessionLocal()
    try:
        ticket = db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} not found for reminder")
            return

        if ticket.status not in [TicketDBStatus.WAITING, TicketDBStatus.SERVING]:
            logger.info(f"Ticket {ticket_id} no longer active, skipping reminder")
            return

        student = db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        if not student or not queue:
            logger.warning(f"Student or queue not found for ticket {ticket_id}")
            return

        # In a real implementation, this would send SMS/email
        # For now, we'll just log it
        logger.info(
            f"REMINDER: Ticket #{ticket.ticket_number} for "
            f"{student.first_name} {student.last_name} in {queue.name}. "
            f"Position: {ticket.position}, Est. wait: {ticket.estimated_wait_time_minutes} min"
        )

        # TODO: Implement actual SMS/email sending
        # send_sms(student.phone, f"Your queue position is {ticket.position}")
        # send_email(student.email, "Queue Reminder", f"...")

    except Exception as exc:
        logger.error(f"Error sending reminder for ticket {ticket_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery.task(bind=True, max_retries=3)
def send_ticket_called(self, ticket_id: int):
    """Notify student that their ticket is being called"""
    db = SessionLocal()
    try:
        ticket = db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} not found for call notification")
            return

        student = db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        if not student or not queue:
            logger.warning(f"Student or queue not found for ticket {ticket_id}")
            return

        logger.info(
            f"CALLED: Ticket #{ticket.ticket_number} for "
            f"{student.first_name} {student.last_name} in {queue.name}. "
            f"Please proceed to the counter."
        )

        # TODO: Implement actual notification
        # send_sms(student.phone, f"Your ticket #{ticket.ticket_number} is now being served at {queue.name}")
        # Emit WebSocket event for real-time UI update
        # emit_ws_event("ticket_called", {"ticket_id": ticket_id, "queue_name": queue.name})

    except Exception as exc:
        logger.error(f"Error sending call notification for ticket {ticket_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery.task
def update_all_wait_times():
    """Periodically update estimated wait times for all queues"""
    db = SessionLocal()
    try:
        queues = db.query(QueueDB).filter(QueueDB.status == "active").all()

        for queue in queues:
            # Update wait times for waiting tickets
            tickets = db.query(TicketDB).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status.in_(["waiting", "serving"])
            ).order_by(TicketDB.position).all()

            # Get service to recalculate wait times
            service = TicketService(db)

            for ticket in tickets:
                # Re-estimate wait time based on current position
                new_wait = service.estimate_wait_time(queue.id, ticket.position)
                if ticket.estimated_wait_time_minutes != new_wait:
                    ticket.estimated_wait_time_minutes = new_wait

            db.commit()

            logger.info(f"Updated wait times for queue {queue.name} ({len(tickets)} tickets)")

    except Exception as exc:
        logger.error(f"Error updating wait times: {exc}")
    finally:
        db.close()


@celery.task
def check_no_show_tickets():
    """Check for tickets that have been waiting too long and mark as no-show"""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta

        # Find tickets that have been waiting/serving for too long
        # For serving tickets: if no completion after 30 minutes
        # For waiting tickets: if position is 1 and not served after 10 minutes

        serving_tickets = db.query(TicketDB).filter(
            TicketDB.status == TicketDBStatus.SERVING,
            TicketDB.served_at.isnot(None)
        ).all()

        for ticket in serving_tickets:
            if ticket.served_at and datetime.utcnow() - ticket.served_at > timedelta(minutes=30):
                logger.info(f"Marking ticket {ticket.id} as no-show (serving timeout)")
                ticket.status = TicketDBStatus.NO_SHOW

        # Also check waiting tickets that were first in line but not served
        # This would need a more sophisticated implementation tracking when they became position 1

        db.commit()

    except Exception as exc:
        logger.error(f"Error checking no-show tickets: {exc}")
    finally:
        db.close()


# How close to the front of the line a waiting ticket must be before it's
# considered "coming up soon" and worth reminding the student about.
REMINDER_POSITION_THRESHOLD = 3


@celery.task
def send_reminder_check():
    """Find waiting tickets close to being served and dispatch a reminder for each"""
    db = SessionLocal()
    try:
        tickets = db.query(TicketDB).filter(
            TicketDB.status == TicketDBStatus.WAITING,
            TicketDB.position.isnot(None),
            TicketDB.position <= REMINDER_POSITION_THRESHOLD,
        ).all()

        for ticket in tickets:
            send_ticket_reminder.delay(ticket.id)

        if tickets:
            logger.info(f"Dispatched reminders for {len(tickets)} ticket(s) coming up soon")

    except Exception as exc:
        logger.error(f"Error checking tickets for reminders: {exc}")
    finally:
        db.close()


@celery.task
def send_queue_closed_notification(queue_id: int):
    """Notify all waiting students when a queue is closed"""
    db = SessionLocal()
    try:
        queue = db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return

        tickets = db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).all()

        for ticket in tickets:
            student = db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
            if student:
                logger.info(
                    f"QUEUE CLOSED NOTIFICATION: {student.first_name} {student.last_name}, "
                    f"your ticket #{ticket.ticket_number} in {queue.name} - queue is now closed"
                )
                # TODO: Send actual notification

    except Exception as exc:
        logger.error(f"Error sending queue closed notification: {exc}")
    finally:
        db.close()


@celery.task
def expire_stale_appointments():
    """Mark booked appointments whose window has fully passed as expired"""
    db = SessionLocal()
    try:
        from app.services.appointment_service import AppointmentService
        service = AppointmentService(db)
        count = service.expire_stale_appointments()
        if count:
            logger.info(f"Expired {count} stale appointment(s)")
    except Exception as exc:
        logger.error(f"Error expiring stale appointments: {exc}")
    finally:
        db.close()