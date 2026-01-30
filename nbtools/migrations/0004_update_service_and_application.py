"""
Migration 0004_update_service_and_application_to_netboxmodel

This migration updates the Service and Application models to align with
NetBoxModel-based definitions by adding the fields normally provided by
NetBoxModel:

  - created (DateTimeField)
  - last_updated (DateTimeField)
  - tags (TaggableManager)      [if used by NetBoxModel]
  - custom_field_data (JSONField)

NOTE:
NetBoxModel is a proxy over Django's Model that injects these fields and
registers the model with NetBox's features (custom fields, tags, etc.).
We emulate the field additions here so the database matches the new
Python model definitions.
"""

from django.db import migrations, models
import taggit.managers
from django.utils import timezone


def set_default_created(apps, schema_editor):
    """
    Backfill a default value for 'created' on existing rows.
    We just use the current time as a safe fallback.
    """
    Service = apps.get_model("nbtools", "Service")
    Application = apps.get_model("nbtools", "Application")
    now = timezone.now()
    Service.objects.filter(created__isnull=True).update(created=now)
    Application.objects.filter(created__isnull=True).update(created=now)


class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0001_initial"),          # for Taggable model (tags)
        ("nbtools", "0003_add_service_and_application"),
    ]

    operations = [
        # ---------------------------------------------------------------------
        # Service model: Add NetBoxModel fields
        # ---------------------------------------------------------------------

        # created
        migrations.AddField(
            model_name="service",
            name="created",
            field=models.DateTimeField(
                auto_now_add=True,
                null=True,
                blank=True,
            ),
            preserve_default=False,
        ),

        # last_updated
        migrations.AddField(
            model_name="service",
            name="last_updated",
            field=models.DateTimeField(
                auto_now=True,
                null=True,
                blank=True,
            ),
            preserve_default=False,
        ),

        # custom_field_data
        migrations.AddField(
            model_name="service",
            name="custom_field_data",
            field=models.JSONField(
                blank=True,
                default=dict,
            ),
        ),

        # tags (TaggableManager on extras.Tag)
        migrations.AddField(
            model_name="service",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="Tags for this object",
                through="extras.TaggedItem",
                to="extras.Tag",
                verbose_name="Tags",
            ),
        ),

        # ---------------------------------------------------------------------
        # Application model: Add NetBoxModel fields
        # ---------------------------------------------------------------------

        # created
        migrations.AddField(
            model_name="application",
            name="created",
            field=models.DateTimeField(
                auto_now_add=True,
                null=True,
                blank=True,
            ),
            preserve_default=False,
        ),

        # last_updated
        migrations.AddField(
            model_name="application",
            name="last_updated",
            field=models.DateTimeField(
                auto_now=True,
                null=True,
                blank=True,
            ),
            preserve_default=False,
        ),

        # custom_field_data
        migrations.AddField(
            model_name="application",
            name="custom_field_data",
            field=models.JSONField(
                blank=True,
                default=dict,
            ),
        ),

        # tags
        migrations.AddField(
            model_name="application",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="Tags for this object",
                through="extras.TaggedItem",
                to="extras.Tag",
                verbose_name="Tags",
            ),
        ),

        # Backfill created timestamps on existing rows
        migrations.RunPython(
            set_default_created,
            reverse_code=migrations.RunPython.noop,
        ),
    ]