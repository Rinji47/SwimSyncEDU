from django.db import models


class CompletionCertificate(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='completion_certificates')
    trainer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='issued_certificates')
    class_booking = models.OneToOneField(
        'classes.ClassBooking',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='completion_certificate',
    )
    private_class = models.OneToOneField(
        'classes.PrivateClass',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='completion_certificate',
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.class_booking:
            return f"Certificate for {self.user.username} - {self.class_booking.class_session.class_name}"
        if self.private_class:
            return f"Certificate for {self.user.username} - Private Class with {self.trainer.username}"
        return f"Certificate for {self.user.username} - No class associated"
