from datetime import datetime, timedelta, timezone
from django.db import models
from accounts.models import User

# Create your models here.
class Pool(models.Model):
    pool_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    capacity = models.IntegerField()
    image_url = models.URLField(max_length=200, blank=True, null=True)
    coordinates = models.CharField(max_length=100)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    

class PoolQuality(models.Model):
    quality_id = models.AutoField(primary_key=True)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='qualities')
    cleanliness_rating = models.IntegerField()
    pH_level = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    water_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    chlorine_level = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pool', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.pool.name} Quality on {self.date}"

class TrainerPoolAssignment(models.Model):
    trainer = models.ForeignKey(User, on_delete=models.CASCADE)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def update_status(self):
        today = timezone.now().date()
        if self.end_date and self.end_date < today:
            if self.is_active:
                self.is_active = False
                self.save(update_fields=['is_active'])