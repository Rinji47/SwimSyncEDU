from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('certificate', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='completioncertificate',
            table='certificate_completioncertificate',
        ),
    ]
