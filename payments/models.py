from django.db import models
import uuid

from accounts.models import User
from classes.models import ClassBooking, ClassSession, PrivateClass


class Payment(models.Model):
    PURPOSE_CHOICES = [
        ('group', 'Group Class'),
        ('private', 'Private Class'),
    ]
    METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Online', 'Online'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    class_session = models.ForeignKey(ClassSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='payments')
    class_booking = models.ForeignKey(ClassBooking, null=True, blank=True, on_delete=models.SET_NULL, related_name='payments')
    private_class = models.ForeignKey(PrivateClass, null=True, blank=True, on_delete=models.SET_NULL, related_name='payments')

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='Online')
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    extra_payload = models.JSONField(null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)

    payment_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.uid} - {self.purpose} - {self.payment_status}"
