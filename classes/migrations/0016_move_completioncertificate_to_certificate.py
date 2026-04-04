from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0015_completioncertificate'),
        ('reviews', '0005_alter_review_certificate'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name='CompletionCertificate',
                ),
            ],
        ),
    ]
