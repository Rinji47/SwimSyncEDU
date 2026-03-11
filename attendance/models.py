from django.db import models
from classes.models import ClassSession, PrivateClass
from accounts.models import User

class TrainerAttendanceRecord(models.Model):
    trainer = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    
    STATUS_CHOICES = [
        ('present', 'Trainer Present'),
        ('absent', 'Trainer Absent'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    def __str__(self):
        return f"{self.trainer.username} - {self.date} - {self.get_status_display()}"
    
class ClassSessionAttendance(models.Model):
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    
    STATUS_CHOICES = [
        ('present', 'Student Present'),
        ('absent', 'Student Absent'),
        ('class_cancelled', 'Class Cancelled'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    marked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='marked_class_attendances')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.username} - {self.class_session.class_name} - {self.date} - {self.status}"
    
class PrivateClassAttendance(models.Model):
    private_class = models.ForeignKey(PrivateClass, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    
    STATUS_CHOICES = [
        ('present', 'Student Present'),
        ('absent', 'Student Absent'),
        ('class_cancelled', 'Class Cancelled'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    marked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='marked_private_class_attendances')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.username} - Private Class with {self.private_class.trainer.username} - {self.date} - {self.status}"
