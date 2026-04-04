import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificate', '0001_initial'),
        ('reviews', '0004_remove_review_trainer'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='review',
                    name='certificate',
                    field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review', to='certificate.completioncertificate'),
                ),
            ],
        ),
    ]
