from django.db import migrations

def create_default_private_class_details(apps, schema_editor):
    PrivateClassDetails = apps.get_model('classes', 'PrivateClassDetails')
    if PrivateClassDetails.objects.count() == 0:
        PrivateClassDetails.objects.create(private_class_price_per_day=300.00)

class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0008_remove_privateclassdetails_price_per_day_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_private_class_details),
    ]
