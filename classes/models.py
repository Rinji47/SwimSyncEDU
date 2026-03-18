from django.db import models
from django.conf import settings
from pool.models import Pool
from accounts.models import User
from datetime import timedelta

# Create your models here.
class ClassType(models.Model):
    class_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=0)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class ClassSession(models.Model):
    trainer = models.ForeignKey(User, on_delete=models.CASCADE)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    class_type = models.ForeignKey(ClassType, on_delete=models.CASCADE)
    substitute_trainer = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='substituted_class_sessions'
    )

    class_name = models.CharField(max_length=100)
    seats = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    is_cancelled = models.BooleanField(default=False)

    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    total_bookings = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        self.total_price = self.class_type.cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.class_name} at {self.pool.name}"
    
class ClassBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    booking_date = models.DateTimeField(auto_now_add=True)
    is_cancelled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} booked {self.class_session.class_name}"

class PrivateClassDetails(models.Model):
    private_class_price_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=300.00)
    created_at = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "Global Admin Settings for Private Classes"

class PrivateClass(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trainer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trainer')
    substitute_trainer = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='substituted_classes'
    )

    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    
    start_date = models.DateField()
    end_date = models.DateField()

    start_time = models.TimeField()
    end_time = models.TimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_cancelled = models.BooleanField(default=False)

    @property
    def weekdays_count(self):
        day_count = 0
        current_day = self.start_date
        while current_day <= self.end_date:
            if current_day.weekday() < 5:
                day_count += 1
            current_day += timedelta(days=1)
        return day_count

    @property
    def total_price(self):
        private_class_details = PrivateClassDetails.objects.order_by('-created_at').first()
        if private_class_details:
            return self.weekdays_count * private_class_details.private_class_price_per_day
        return 0

    def __str__(self):
        return f"{self.user.username}'s private class with {self.trainer.username}"


class CompletionCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='completion_certificates')
    trainer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_certificates')

    class_booking = models.OneToOneField(
        ClassBooking, 
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='completion_certificate'
    )

    private_class = models.OneToOneField(
        PrivateClass,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='completion_certificate'
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.class_booking:
            return f"Certificate for {self.user.username} - {self.class_booking.class_session.class_name}"
        elif self.private_class:
            return f"Certificate for {self.user.username} - Private Class with {self.trainer.username}"
        else:
            return f"Certificate for {self.user.username} - No class associated"