from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('certificate', '0001_initial'),
        ('reviews', '0005_alter_review_certificate'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='completioncertificate',
            table='certificate_completioncertificate',
        ),
    ]
