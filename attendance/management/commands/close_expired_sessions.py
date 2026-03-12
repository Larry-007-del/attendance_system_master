"""
Management command to auto-close expired attendance sessions.

Sessions are considered expired when:
    now > created_at + duration_hours

Run periodically via cron / Render Cron Job / Celery Beat:
    python manage.py close_expired_sessions
    python manage.py close_expired_sessions --notify   # also send missed-attendance alerts
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from attendance.models import Attendance, AttendanceToken

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Close attendance sessions that have exceeded their duration and deactivate related tokens.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--notify',
            action='store_true',
            default=False,
            help='Send missed-attendance notifications to absent students.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be closed without making changes.',
        )

    def handle(self, *args, **options):
        notify = options['notify']
        dry_run = options['dry_run']
        now = timezone.now()

        # Find sessions that are still marked active but have exceeded their duration
        expired_sessions = []
        active_sessions = Attendance.objects.filter(is_active=True).select_related('course')

        for session in active_sessions:
            expiry = session.created_at + timedelta(hours=session.duration_hours)
            if now >= expiry:
                expired_sessions.append(session)

        if not expired_sessions:
            self.stdout.write(self.style.SUCCESS('No expired sessions found.'))
            return

        self.stdout.write(f'Found {len(expired_sessions)} expired session(s).')

        if dry_run:
            for session in expired_sessions:
                self.stdout.write(
                    f'  [DRY-RUN] Would close: {session.course.name} '
                    f'(ID {session.pk}, created {session.created_at:%Y-%m-%d %H:%M})'
                )
            return

        closed_count = 0
        token_count = 0

        for session in expired_sessions:
            # Close the session
            session.is_active = False
            session.ended_at = session.created_at + timedelta(hours=session.duration_hours)
            session.save(update_fields=['is_active', 'ended_at', 'updated_at'])
            closed_count += 1

            # Deactivate related tokens
            tokens_updated = AttendanceToken.objects.filter(
                course=session.course,
                is_active=True,
            ).update(is_active=False)
            token_count += tokens_updated

            self.stdout.write(
                f'  Closed: {session.course.name} '
                f'(ID {session.pk}, {tokens_updated} token(s) deactivated)'
            )

            # Send missed-attendance notifications if requested
            if notify:
                try:
                    from attendance.notification_service import send_attendance_missed_notifications
                    send_attendance_missed_notifications(session)
                    self.stdout.write(f'    Sent missed-attendance notifications.')
                except Exception as exc:
                    logger.exception('Failed to send notifications for session %s', session.pk)
                    self.stderr.write(f'    Notification error: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Closed {closed_count} session(s), deactivated {token_count} token(s).'
        ))
