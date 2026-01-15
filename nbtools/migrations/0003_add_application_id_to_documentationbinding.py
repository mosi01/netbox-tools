from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('nbtools', '0002_update_sharepointconfig'),  # Or your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='documentationbinding',
            name='application_id',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
