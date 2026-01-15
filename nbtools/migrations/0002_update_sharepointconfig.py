from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('nbtools', '0001_initial'),
    ]

    operations = [
        # Remove old fields
        migrations.RemoveField(
            model_name='sharepointconfig',
            name='username',
        ),
        migrations.RemoveField(
            model_name='sharepointconfig',
            name='password',
        ),

        # Add new fields
        migrations.AddField(
            model_name='sharepointconfig',
            name='application_id',
            field=models.CharField(max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sharepointconfig',
            name='client_id',
            field=models.CharField(max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sharepointconfig',
            name='client_secret',
            field=models.CharField(max_length=255, default=''),
            preserve_default=False,
        ),
    ]
