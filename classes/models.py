from django.db import models
from django.conf import settings
from pool.models import Pool

# Create your models here.
class ClassType(models.Model):
    class_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class ClassSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    class_type = models.ForeignKey(ClassType, on_delete=models.CASCADE)

    class_name = models.CharField(max_length=100)
    total_sessions = models.IntegerField()
    seats = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    is_cancelled = models.BooleanField(default=False)

    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_price = self.class_type.cost * self.total_sessions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.class_name} at {self.pool.name}"