import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('classes', '0015_completioncertificate'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='CompletionCertificate',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('issued_at', models.DateTimeField(auto_now_add=True)),
                        ('class_booking', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='completion_certificate', to='classes.classbooking')),
                        ('private_class', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='completion_certificate', to='classes.privateclass')),
                        ('trainer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='issued_certificates', to=settings.AUTH_USER_MODEL)),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='completion_certificates', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'classes_completioncertificate',
                    },
                ),
            ],
        ),
    ]
