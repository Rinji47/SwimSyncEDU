from django.db import models
from accounts.models import User

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    certificate = models.OneToOneField(
        'certificate.CompletionCertificate',
        on_delete=models.CASCADE,
        related_name='review'
    )

    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        if self.certificate.class_booking:
            trainer = self.certificate.class_booking.class_session.trainer
        elif self.certificate.private_class:
            trainer = self.certificate.private_class.trainer
        else:
            trainer = None

        trainer_name = trainer.username if trainer else 'Unknown trainer'
        return f'Review by {self.user.username} for {trainer_name} - Rating: {self.rating}'
