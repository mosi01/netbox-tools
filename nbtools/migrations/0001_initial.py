from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SharePointConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_url', models.URLField()),                
                ('application_id', models.CharField(max_length=255)),
                ('client_id', models.CharField(max_length=255)),
                ('client_secret', models.CharField(max_length=255)),
                ('folder_mappings', models.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name='DocumentationBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=255)),
                ('server_name', models.CharField(max_length=255, db_index=True)),
                ('application_name', models.CharField(max_length=255, null=True, blank=True)),
                ('file_name', models.CharField(max_length=255)),
                ('version', models.CharField(max_length=50)),
                ('file_type', models.CharField(max_length=50)),
                ('sharepoint_url', models.URLField()),
            ],
        ),
    ]
