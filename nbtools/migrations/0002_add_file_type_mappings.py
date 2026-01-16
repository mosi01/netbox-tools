from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('nbtools', '0001_initial'),  # Adjust if your previous migration name differs
    ]

    operations = [
        migrations.AddField(
            model_name='sharepointconfig',
            name='file_type_mappings',
            field=models.JSONField(default=dict),
        ),
    ]
