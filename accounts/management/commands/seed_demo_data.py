import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from attendance.models import (
    ClassSessionAttendance,
    PrivateClassAttendance,
    TrainerAttendanceRecord,
)
from certificate.models import CompletionCertificate
from classes.models import (
    ClassBooking,
    ClassSession,
    ClassType,
    PrivateClass,
    PrivateClassDetails,
)
from payments.models import Payment
from pool.models import Pool, PoolQuality, TrainerPoolAssignment
from reviews.models import Review


DEMO_DOMAIN = "demo.swimsyncedu.local"
DEMO_PASSWORD = "demo12345"
PROFILE_PICTURE_PATH = "profile_pics/Screenshot_2026-02-03_235012.png"
SIGNATURE_PATH = "signatures/img.png"


class Command(BaseCommand):
    help = "Seed the database with a large, realistic demo dataset for supervisor demos and testing."

    def add_arguments(self, parser):
        parser.add_argument("--members", type=int, default=36)
        parser.add_argument("--trainers", type=int, default=8)
        parser.add_argument("--password", type=str, default=DEMO_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        self.random = random.Random(20260407)
        self.password = options["password"]
        self.today = timezone.localdate()
        self.member_count = max(18, options["members"])
        self.trainer_count = max(4, options["trainers"])

        self._clear_previous_demo_data()
        self._ensure_private_class_settings()

        admin = self._create_demo_admin()
        trainers = self._create_demo_trainers()
        members = self._create_demo_members()
        pools = self._create_demo_pools()
        class_types = self._create_demo_class_types()

        self._create_pool_assignments(trainers, pools)
        sessions = self._create_group_sessions(trainers, pools, class_types)
        private_classes = self._create_private_classes(trainers, pools, members)
        bookings = self._create_group_bookings_and_payments(sessions, members)
        self._create_private_payments(private_classes)
        self._create_pool_quality_history(pools)
        self._create_attendance_history(trainers, sessions, private_classes, bookings)
        certificates = self._create_certificates(bookings, private_classes)
        self._create_reviews(certificates)

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write(f"Admin login: demo_admin / {self.password}")
        self.stdout.write(f"Trainer login: {trainers[0].username} / {self.password}")
        self.stdout.write(f"Member login: {members[0].username} / {self.password}")
        self.stdout.write(
            f"Created {len(trainers)} trainers, {len(members)} members, {len(pools)} pools, "
            f"{len(sessions)} group sessions, {len(private_classes)} private classes."
        )

    def _clear_previous_demo_data(self):
        demo_users = User.objects.filter(email__iendswith=f"@{DEMO_DOMAIN}")
        demo_pools = Pool.objects.filter(name__startswith="Demo ")
        demo_class_types = ClassType.objects.filter(name__startswith="Demo ")
        demo_sessions = ClassSession.objects.filter(
            trainer__in=demo_users
        ) | ClassSession.objects.filter(pool__in=demo_pools) | ClassSession.objects.filter(class_type__in=demo_class_types)
        demo_private_classes = PrivateClass.objects.filter(
            user__in=demo_users
        ) | PrivateClass.objects.filter(trainer__in=demo_users) | PrivateClass.objects.filter(pool__in=demo_pools)

        Payment.objects.filter(
            user__in=demo_users
        ).delete()
        Review.objects.filter(
            certificate__user__in=demo_users
        ).delete()
        CompletionCertificate.objects.filter(
            user__in=demo_users
        ).delete()
        ClassSessionAttendance.objects.filter(
            student__in=demo_users
        ).delete()
        PrivateClassAttendance.objects.filter(
            student__in=demo_users
        ).delete()
        TrainerAttendanceRecord.objects.filter(
            trainer__in=demo_users
        ).delete()
        ClassBooking.objects.filter(
            user__in=demo_users
        ).delete()
        ClassBooking.objects.filter(
            class_session__in=demo_sessions
        ).delete()
        PrivateClass.objects.filter(pk__in=demo_private_classes.values_list("pk", flat=True)).delete()
        ClassSession.objects.filter(pk__in=demo_sessions.values_list("pk", flat=True)).delete()
        TrainerPoolAssignment.objects.filter(trainer__in=demo_users).delete()
        PoolQuality.objects.filter(pool__in=demo_pools).delete()
        demo_pools.delete()
        demo_class_types.delete()
        demo_users.delete()

    def _ensure_private_class_settings(self):
        if not PrivateClassDetails.objects.exists():
            PrivateClassDetails.objects.create(private_class_price_per_day=Decimal("300.00"))

    def _create_demo_admin(self):
        admin = User.objects.create_superuser(
            username="demo_admin",
            email=f"demo_admin@{DEMO_DOMAIN}",
            password=self.password,
            full_name="Demo Admin",
            phone="9800000000",
            gender="Other",
            date_of_birth=date(1995, 1, 15),
            profile_picture=PROFILE_PICTURE_PATH,
        )
        admin.digital_signature = SIGNATURE_PATH
        admin.save(update_fields=["digital_signature"])
        return admin

    def _create_demo_trainers(self):
        trainer_specs = [
            ("Aarav", "Freestyle & Stroke Correction"),
            ("Saanvi", "Beginner Safety"),
            ("Ishaan", "Kids Confidence Training"),
            ("Anaya", "Breathing Technique"),
            ("Reyansh", "Butterfly & Endurance"),
            ("Diya", "Teen Performance"),
            ("Kabir", "Adult Beginner Coaching"),
            ("Aadhya", "Private Competitive Prep"),
            ("Vivaan", "Backstroke Technique"),
            ("Siya", "Water Confidence"),
        ]
        trainers = []
        for index in range(self.trainer_count):
            first_name, specialization = trainer_specs[index % len(trainer_specs)]
            full_name = f"{first_name} Trainer {index + 1}"
            trainer = User.objects.create_user(
                username=f"demo_trainer_{index + 1}",
                email=f"demo_trainer_{index + 1}@{DEMO_DOMAIN}",
                password=self.password,
                role="trainer",
                full_name=full_name,
                phone=f"98110{index:05d}",
                gender="Female" if index % 2 else "Male",
                date_of_birth=date(1988 + (index % 8), (index % 12) + 1, (index % 20) + 1),
                experience_years=3 + (index % 9),
                specialization=specialization,
                profile_picture=PROFILE_PICTURE_PATH,
                digital_signature=SIGNATURE_PATH,
                is_active=True,
            )
            trainers.append(trainer)
        return trainers

    def _create_demo_members(self):
        first_names = [
            "Aarya", "Pranav", "Nisha", "Rohan", "Sneha", "Sujal", "Mina", "Kiran", "Sita",
            "Aman", "Pema", "Riya", "Ayush", "Nabin", "Sanjana", "Yuvraj", "Asmita", "Alina",
            "Roshan", "Niraj", "Elina", "Saroj", "Suman", "Tara", "Bikash", "Aakriti",
        ]
        last_names = [
            "Sharma", "Thapa", "Karki", "Gurung", "Rai", "Tamang", "Shrestha", "Bhandari",
            "Lama", "Adhikari", "Maharjan", "KC",
        ]
        members = []
        for index in range(self.member_count):
            first_name = first_names[index % len(first_names)]
            last_name = last_names[index % len(last_names)]
            member = User.objects.create_user(
                username=f"demo_member_{index + 1}",
                email=f"demo_member_{index + 1}@{DEMO_DOMAIN}",
                password=self.password,
                role="user",
                full_name=f"{first_name} {last_name}",
                phone=f"98220{index:05d}",
                gender="Female" if index % 2 else "Male",
                date_of_birth=date(2000 + (index % 6), ((index + 3) % 12) + 1, ((index + 8) % 20) + 1),
                profile_picture=PROFILE_PICTURE_PATH if index % 3 == 0 else None,
                is_active=index % 11 != 0,
            )
            members.append(member)
        return members

    def _create_demo_pools(self):
        pool_specs = [
            ("Demo Boudha Aqua Center", "Boudha, Kathmandu", 28, "27.7215,85.3616", False),
            ("Demo Patan Splash Hub", "Patan, Lalitpur", 24, "27.6710,85.3256", False),
            ("Demo Bhaktapur Swim Arena", "Suryabinayak, Bhaktapur", 32, "27.6718,85.4298", False),
            ("Demo Kirtipur Family Pool", "Kirtipur, Kathmandu", 20, "27.6672,85.2775", False),
            ("Demo Baneshwor Training Pool", "New Baneshwor, Kathmandu", 26, "27.6909,85.3436", False),
            ("Demo Tokha Reserve Pool", "Tokha, Kathmandu", 18, "27.7472,85.3294", True),
        ]
        pools = []
        for name, address, capacity, coordinates, is_closed in pool_specs:
            pools.append(
                Pool.objects.create(
                    name=name,
                    address=address,
                    capacity=capacity,
                    coordinates=coordinates,
                    is_closed=is_closed,
                )
            )
        return pools

    def _create_demo_class_types(self):
        class_type_specs = [
            ("Demo Beginner Basics", "Water confidence, kickboard drills, and safety basics.", Decimal("2500.00"), 12),
            ("Demo Kids Starter", "Confidence-focused beginner group class for children.", Decimal("2200.00"), 10),
            ("Demo Intermediate Technique", "Stroke correction, breathing rhythm, and pacing.", Decimal("3200.00"), 15),
            ("Demo Adult Fitness Swim", "Lap-focused training for adults building endurance.", Decimal("3600.00"), 18),
            ("Demo Competitive Prep", "Starts, turns, and timed sets for competitive swimmers.", Decimal("5000.00"), 21),
            ("Demo Recovery Swim", "Low-intensity mobility and recovery-focused sessions.", Decimal("1800.00"), 8),
        ]
        class_types = []
        for name, description, cost, duration_days in class_type_specs:
            class_types.append(
                ClassType.objects.create(
                    name=name,
                    description=description,
                    cost=cost,
                    duration_days=duration_days,
                    is_closed=False,
                )
            )
        return class_types

    def _create_pool_assignments(self, trainers, pools):
        for index, trainer in enumerate(trainers):
            current_pool = pools[index % max(1, len(pools) - 1)]
            TrainerPoolAssignment.objects.create(
                trainer=trainer,
                pool=current_pool,
                start_date=self.today - timedelta(days=90 - (index * 3)),
                end_date=None,
                is_active=True,
            )
            if index % 3 == 0:
                old_pool = pools[(index + 2) % max(1, len(pools) - 1)]
                TrainerPoolAssignment.objects.create(
                    trainer=trainer,
                    pool=old_pool,
                    start_date=self.today - timedelta(days=180),
                    end_date=self.today - timedelta(days=95 - index),
                    is_active=False,
                )

    def _create_group_sessions(self, trainers, pools, class_types):
        sessions = []
        sessions.extend(self._build_sessions(trainers, pools, class_types, "past", 10))
        sessions.extend(self._build_sessions(trainers, pools, class_types, "active", 8))
        sessions.extend(self._build_sessions(trainers, pools, class_types, "upcoming", 10))
        sessions.extend(self._build_sessions(trainers, pools, class_types, "cancelled", 4))
        return sessions

    def _build_sessions(self, trainers, pools, class_types, mode, count):
        sessions = []
        time_slots = [
            (time(6, 30), time(7, 30)),
            (time(8, 0), time(9, 0)),
            (time(10, 0), time(11, 0)),
            (time(15, 30), time(16, 30)),
            (time(17, 0), time(18, 0)),
        ]
        open_pools = [pool for pool in pools if not pool.is_closed]
        for index in range(count):
            trainer = trainers[index % len(trainers)]
            pool = open_pools[index % len(open_pools)]
            class_type = class_types[index % len(class_types)]
            duration = timedelta(days=class_type.duration_days)
            if mode == "past":
                start_date = self.today - timedelta(days=55 + (index * 4))
            elif mode == "active":
                start_date = self.today - timedelta(days=max(2, class_type.duration_days // 2) - (index % 2))
            elif mode == "upcoming":
                start_date = self.today + timedelta(days=2 + (index * 2))
            else:
                start_date = self.today + timedelta(days=3 + index)
            end_date = start_date + duration
            start_time, end_time = time_slots[index % len(time_slots)]
            substitute = None
            if mode in {"active", "past"} and index % 4 == 0:
                substitute = trainers[(index + 1) % len(trainers)]
            session = ClassSession.objects.create(
                trainer=trainer,
                substitute_trainer=substitute,
                pool=pool,
                class_type=class_type,
                class_name=f"{class_type.name.replace('Demo ', '')} Batch {index + 1}",
                seats=10 + (index % 6),
                start_date=start_date,
                end_date=end_date,
                start_time=start_time,
                end_time=end_time,
                is_cancelled=mode == "cancelled",
                total_price=class_type.cost,
            )
            sessions.append(session)
        return sessions

    def _create_private_classes(self, trainers, pools, members):
        private_classes = []
        open_pools = [pool for pool in pools if not pool.is_closed]
        time_slots = [
            (time(7, 0), time(8, 0)),
            (time(9, 0), time(10, 0)),
            (time(16, 0), time(17, 0)),
            (time(18, 0), time(19, 0)),
        ]
        for index in range(12):
            if index < 4:
                start_date = self.today - timedelta(days=28 + (index * 5))
                end_date = start_date + timedelta(days=9)
            elif index < 8:
                start_date = self.today - timedelta(days=4 + index)
                end_date = self.today + timedelta(days=6 + index)
            else:
                start_date = self.today + timedelta(days=3 + index)
                end_date = start_date + timedelta(days=8)
            start_time, end_time = time_slots[index % len(time_slots)]
            private_classes.append(
                PrivateClass.objects.create(
                    user=members[index % len(members)],
                    trainer=trainers[(index + 2) % len(trainers)],
                    substitute_trainer=trainers[(index + 3) % len(trainers)] if index in {5, 6} else None,
                    pool=open_pools[index % len(open_pools)],
                    start_date=start_date,
                    end_date=end_date,
                    start_time=start_time,
                    end_time=end_time,
                    is_cancelled=index in {10, 11},
                )
            )
        return private_classes

    def _create_group_bookings_and_payments(self, sessions, members):
        bookings = []
        member_cursor = 0
        completed_statuses = ["Completed", "Completed", "Completed", "Completed", "Pending", "Cancelled", "Failed"]
        for index, session in enumerate(sessions):
            if session.is_cancelled:
                continue
            booking_target = min(session.seats - 1, 4 + (index % 5))
            for seat in range(booking_target):
                member = members[(member_cursor + seat) % len(members)]
                booking = ClassBooking.objects.create(user=member, class_session=session, is_cancelled=False)
                bookings.append(booking)
                payment_status = completed_statuses[(index + seat) % len(completed_statuses)]
                payment_method = ["Online", "Card", "Cash"][(index + seat) % 3]
                payment = Payment.objects.create(
                    user=member,
                    purpose="group",
                    class_session=session,
                    class_booking=booking if payment_status == "Completed" else None,
                    amount=session.total_price,
                    tax_amount=(session.total_price * Decimal("0.13")).quantize(Decimal("0.01")),
                    service_charge=Decimal("0.00"),
                    delivery_charge=Decimal("0.00"),
                    total_amount=(session.total_price * Decimal("1.13")).quantize(Decimal("0.01")),
                    payment_method=payment_method,
                    payment_status=payment_status,
                )
                self._set_payment_datetime(payment, session.start_date - timedelta(days=2))
                if payment_status != "Completed":
                    booking.is_cancelled = payment_status in {"Cancelled", "Failed"}
                    booking.save(update_fields=["is_cancelled"])
            session.total_bookings = ClassBooking.objects.filter(class_session=session, is_cancelled=False).count()
            session.save(update_fields=["total_bookings"])
            member_cursor += booking_target
        return bookings

    def _create_private_payments(self, private_classes):
        for index, private_class in enumerate(private_classes):
            status = ["Completed", "Completed", "Pending", "Cancelled", "Failed"][index % 5]
            payment = Payment.objects.create(
                user=private_class.user,
                purpose="private",
                private_class=private_class if status == "Completed" else None,
                amount=Decimal(private_class.total_price).quantize(Decimal("0.01")),
                tax_amount=(Decimal(private_class.total_price) * Decimal("0.13")).quantize(Decimal("0.01")),
                service_charge=Decimal("0.00"),
                delivery_charge=Decimal("0.00"),
                total_amount=(Decimal(private_class.total_price) * Decimal("1.13")).quantize(Decimal("0.01")),
                payment_method=["Online", "Card", "Cash"][index % 3],
                payment_status=status,
                extra_payload={
                    "pool_id": private_class.pool_id,
                    "trainer_id": private_class.trainer_id,
                    "start_date": private_class.start_date.isoformat(),
                    "end_date": private_class.end_date.isoformat(),
                    "start_time": private_class.start_time.strftime("%H:%M"),
                    "end_time": private_class.end_time.strftime("%H:%M"),
                },
            )
            self._set_payment_datetime(payment, private_class.start_date - timedelta(days=1))

    def _create_pool_quality_history(self, pools):
        for pool_index, pool in enumerate(pools):
            for days_back in range(7):
                quality_date = self.today - timedelta(days=days_back)
                PoolQuality.objects.create(
                    pool=pool,
                    cleanliness_rating=max(2, 5 - ((pool_index + days_back) % 4)),
                    pH_level=Decimal("7.10") + Decimal(pool_index) / Decimal("100"),
                    water_temperature=Decimal("26.50") + Decimal(days_back) / Decimal("10"),
                    chlorine_level=Decimal("1.20") + Decimal(pool_index + days_back) / Decimal("20"),
                    date=quality_date,
                )

    def _create_attendance_history(self, trainers, sessions, private_classes, bookings):
        self._create_trainer_attendance(trainers)
        active_bookings_by_session = {}
        for booking in bookings:
            if booking.is_cancelled:
                continue
            active_bookings_by_session.setdefault(booking.class_session_id, []).append(booking)

        for index, session in enumerate(sessions):
            if session.is_cancelled:
                continue
            session_dates = self._weekday_dates_between(
                session.start_date,
                min(session.end_date, self.today),
                max_days=5 if session.end_date < self.today else 2,
            )
            for session_date in session_dates:
                for booking_index, booking in enumerate(active_bookings_by_session.get(session.id, [])):
                    status = "present"
                    if (booking_index + index + session_date.day) % 7 == 0:
                        status = "absent"
                    if index % 6 == 0 and booking_index == 0 and session_date == session_dates[-1]:
                        status = "class_cancelled"
                    ClassSessionAttendance.objects.create(
                        class_session=session,
                        student=booking.user,
                        date=session_date,
                        status=status,
                        marked_by=session.substitute_trainer or session.trainer,
                    )

        for index, private_class in enumerate(private_classes):
            if private_class.is_cancelled:
                continue
            attendance_dates = self._weekday_dates_between(
                private_class.start_date,
                min(private_class.end_date, self.today),
                max_days=4 if private_class.end_date < self.today else 2,
            )
            for attendance_date in attendance_dates:
                status = "present"
                if (index + attendance_date.day) % 6 == 0:
                    status = "absent"
                if index % 5 == 0 and attendance_date == attendance_dates[-1]:
                    status = "class_cancelled"
                PrivateClassAttendance.objects.create(
                    private_class=private_class,
                    student=private_class.user,
                    date=attendance_date,
                    status=status,
                    marked_by=private_class.substitute_trainer or private_class.trainer,
                )

    def _create_trainer_attendance(self, trainers):
        for trainer_index, trainer in enumerate(trainers):
            for days_back in range(0, 21):
                attendance_date = self.today - timedelta(days=days_back)
                if attendance_date.weekday() >= 5:
                    continue
                status = "present"
                if days_back in {3, 11} and trainer_index % 3 == 0:
                    status = "absent"
                TrainerAttendanceRecord.objects.create(
                    trainer=trainer,
                    date=attendance_date,
                    status=status,
                )

    def _create_certificates(self, bookings, private_classes):
        certificates = []
        ended_bookings = [
            booking for booking in bookings
            if not booking.is_cancelled and booking.class_session.end_date < self.today
        ]
        for index, booking in enumerate(ended_bookings):
            if index % 3 == 2:
                continue
            certificates.append(
                CompletionCertificate.objects.create(
                    user=booking.user,
                    trainer=booking.class_session.substitute_trainer or booking.class_session.trainer,
                    class_booking=booking,
                )
            )
        for index, private_class in enumerate(private_classes):
            if private_class.is_cancelled or private_class.end_date >= self.today or index % 2 == 1:
                continue
            certificates.append(
                CompletionCertificate.objects.create(
                    user=private_class.user,
                    trainer=private_class.substitute_trainer or private_class.trainer,
                    private_class=private_class,
                )
            )
        return certificates

    def _create_reviews(self, certificates):
        comments = [
            "Clear instructions and really supportive during the difficult drills.",
            "Great energy in class and easy to follow even as a beginner.",
            "Helped a lot with breathing rhythm and confidence in deeper water.",
            "Good trainer and very patient with corrections.",
            "The sessions felt organized and motivating every time.",
        ]
        for index, certificate in enumerate(certificates):
            if index % 4 == 3:
                continue
            Review.objects.create(
                user=certificate.user,
                certificate=certificate,
                rating=5 - (index % 3),
                comment=comments[index % len(comments)],
            )

    def _weekday_dates_between(self, start_date, end_date, max_days):
        dates = []
        current = start_date
        while current <= end_date and len(dates) < max_days:
            if current.weekday() < 5:
                dates.append(current)
            current += timedelta(days=1)
        return dates

    def _set_payment_datetime(self, payment, payment_day):
        aware_dt = timezone.make_aware(datetime.combine(payment_day, time(9, 30)))
        Payment.objects.filter(pk=payment.pk).update(payment_date=aware_dt)
