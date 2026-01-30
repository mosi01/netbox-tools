"""
Migration 0004_update_service_and_application

This migration updates the Service and Application models to align with
their NetBoxModel-based definitions by adding the fields normally
provided by NetBoxModel:

    * created (DateTimeField)
    * last_updated (DateTimeField)
    * custom_field_data (JSONField)

We intentionally do NOT add a tags field here, because tagging is handled
via NetBox's tagging framework with a shared extras.Tag / extras.TaggedItem
schema, and the TaggableManager field on NetBoxModel will bind to those.

Prerequisites:
  * 0003_add_service_and_application has been applied and has created
    the Service and Application tables.
"""

from django.db import migrations, models
from django.utils import timezone


def backfill_created_timestamps(apps, schema_editor):
    """
    Backfill 'created' with a non-null value on existing Service and
    Application records.

    We simply set created = now() for any rows where it is NULL.
    This avoids issues where NetBox expects a non-null created field.
    """
    Service = apps.get_model("nbtools", "Service")
    Application = apps.get_model("nbtools", "Application")

    now = timezone.now()

    Service.objects.filter(created__isnull=True).update(created=now)
    Application.objects.filter(created__isnull=True).update(created=now)


class Migration(migrations.Migration):

    dependencies = [
        ("nbtools", "0003_add_service_and_application"),
    ]

    operations = [

        # ------------------------------------------------------------------
        # Service model: Add NetBoxModel-like fields
        # ------------------------------------------------------------------

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

        migrations.AddField(
            model_name="service",
            name="custom_field_data",
            field=models.JSONField(
                default=dict,
                blank=True,
            ),
        ),

        # ------------------------------------------------------------------
        # Application model: Add NetBoxModel-like fields
        # ------------------------------------------------------------------

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

        migrations.AddField(
            model_name="application",
            name="custom_field_data",
            field=models.JSONField(
                default=dict,
                blank=True,
            ),
        ),

        # ------------------------------------------------------------------
        # Backfill created timestamps on existing rows
        # ------------------------------------------------------------------
        migrations.RunPython(
            backfill_created_timestamps,
            reverse_code=migrations.RunPython.noop,
        ),
    ]