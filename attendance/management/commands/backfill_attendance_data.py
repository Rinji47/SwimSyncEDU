from datetime import timedelta

from django.core.management.base import BaseCommand

from accounts.models import User
from attendance.models import (
    ClassSessionAttendance,
    PrivateClassAttendance,
    TrainerAttendanceRecord,
)
from classes.models import ClassBooking, ClassSession, PrivateClass


class Command(BaseCommand):
    help = 'Fill missing attendance data for existing class sessions, private classes, and trainers.'

    def handle(self, *args, **options):
        bookings_created = self._ensure_group_class_bookings()
        class_records_created = self._fill_group_class_attendance()
        private_records_created = self._fill_private_class_attendance()
        trainer_records_created = self._fill_trainer_attendance()

        self.stdout.write(self.style.SUCCESS('Attendance backfill completed.'))
        self.stdout.write(f'Group class bookings added: {bookings_created}')
        self.stdout.write(f'Group class attendance added: {class_records_created}')
        self.stdout.write(f'Private class attendance added: {private_records_created}')
        self.stdout.write(f'Trainer attendance added: {trainer_records_created}')

    def _ensure_group_class_bookings(self):
        created_count = 0
        members = list(User.objects.filter(role='user', is_active=True).order_by('user_id'))
        if not members:
            return 0

        member_index = 0
        sessions = ClassSession.objects.order_by('start_date', 'start_time')

        for session in sessions:
            active_bookings = ClassBooking.objects.filter(
                class_session=session,
                is_cancelled=False,
            )

            if active_bookings.exists():
                continue

            seats_left = session.seats - session.total_bookings
            if seats_left <= 0:
                continue

            bookings_to_create = min(3, seats_left, len(members))
            for _ in range(bookings_to_create):
                member = members[member_index % len(members)]
                member_index += 1

                booking, created = ClassBooking.objects.get_or_create(
                    user=member,
                    class_session=session,
                    defaults={'is_cancelled': False},
                )
                if created:
                    created_count += 1

            session.total_bookings = ClassBooking.objects.filter(
                class_session=session,
                is_cancelled=False,
            ).count()
            session.save(update_fields=['total_bookings'])

        return created_count

    def _fill_group_class_attendance(self):
        created_count = 0
        sessions = ClassSession.objects.select_related('trainer').order_by('start_date', 'start_time')

        for session in sessions:
            bookings = ClassBooking.objects.filter(
                class_session=session,
                is_cancelled=False,
            ).select_related('user')

            if not bookings.exists():
                continue

            attendance_dates = self._weekday_dates_between(session.start_date, session.end_date)
            marked_by = session.substitute_trainer or session.trainer

            for attendance_date in attendance_dates:
                for booking in bookings:
                    status = self._pick_group_status(session, booking, attendance_date)
                    _, created = ClassSessionAttendance.objects.get_or_create(
                        class_session=session,
                        student=booking.user,
                        date=attendance_date,
                        defaults={
                            'status': status,
                            'marked_by': marked_by,
                        },
                    )
                    if created:
                        created_count += 1

        return created_count

    def _fill_private_class_attendance(self):
        created_count = 0
        private_classes = PrivateClass.objects.select_related('trainer', 'user').order_by('start_date', 'start_time')

        for private_class in private_classes:
            attendance_dates = self._weekday_dates_between(private_class.start_date, private_class.end_date)
            marked_by = private_class.substitute_trainer or private_class.trainer

            for attendance_date in attendance_dates:
                status = self._pick_private_status(private_class, attendance_date)
                _, created = PrivateClassAttendance.objects.get_or_create(
                    private_class=private_class,
                    student=private_class.user,
                    date=attendance_date,
                    defaults={
                        'status': status,
                        'marked_by': marked_by,
                    },
                )
                if created:
                    created_count += 1

        return created_count

    def _fill_trainer_attendance(self):
        created_count = 0
        trainers = User.objects.filter(role='trainer', is_active=True)
        trainer_date_map = {}

        for session in ClassSession.objects.select_related('trainer', 'substitute_trainer'):
            self._add_date_range(trainer_date_map, session.trainer_id, session.start_date, session.end_date)
            if session.substitute_trainer_id:
                self._add_date_range(trainer_date_map, session.substitute_trainer_id, session.start_date, session.end_date)

        for private_class in PrivateClass.objects.select_related('trainer', 'substitute_trainer'):
            self._add_date_range(trainer_date_map, private_class.trainer_id, private_class.start_date, private_class.end_date)
            if private_class.substitute_trainer_id:
                self._add_date_range(trainer_date_map, private_class.substitute_trainer_id, private_class.start_date, private_class.end_date)

        for trainer in trainers:
            attendance_dates = sorted(trainer_date_map.get(trainer.pk, set()))
            for attendance_date in attendance_dates:
                status = self._pick_trainer_status(trainer.pk, attendance_date)
                _, created = TrainerAttendanceRecord.objects.get_or_create(
                    trainer=trainer,
                    date=attendance_date,
                    defaults={'status': status},
                )
                if created:
                    created_count += 1

        return created_count

    def _add_date_range(self, trainer_date_map, trainer_id, start_date, end_date):
        if not trainer_id:
            return

        trainer_date_map.setdefault(trainer_id, set())
        for attendance_date in self._weekday_dates_between(start_date, end_date):
            trainer_date_map[trainer_id].add(attendance_date)

    def _weekday_dates_between(self, start_date, end_date):
        dates = []
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:
                dates.append(current_date)
            current_date += timedelta(days=1)
        return dates

    def _pick_group_status(self, session, booking, attendance_date):
        if session.is_cancelled:
            return 'class_cancelled'
        if (session.id + booking.user_id + attendance_date.day) % 11 == 0:
            return 'class_cancelled'
        if (session.id + booking.user_id + attendance_date.day) % 4 == 0:
            return 'absent'
        return 'present'

    def _pick_private_status(self, private_class, attendance_date):
        if private_class.is_cancelled:
            return 'class_cancelled'
        if (private_class.id + attendance_date.day) % 9 == 0:
            return 'class_cancelled'
        if (private_class.id + attendance_date.day) % 3 == 0:
            return 'absent'
        return 'present'

    def _pick_trainer_status(self, trainer_id, attendance_date):
        if (trainer_id + attendance_date.day) % 8 == 0:
            return 'absent'
        return 'present'
