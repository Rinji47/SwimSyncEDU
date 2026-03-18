from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0015_completioncertificate'),
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='certificate',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='review',
                to='classes.completioncertificate',
            ),
        ),
    ]
