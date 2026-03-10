"""
Migration 0005_add_tags_fields

This migration introduces explicit TaggableManager fields for the
Service and Application models.

Note:
NetBoxModel (NetBox 4.5) does NOT automatically add a `tags` field.
Therefore the plugin models must declare it explicitly, and the database
schema must contain these fields in the migration history.

This migration adds:

    * Service.tags      (related_name="nbtools_service_tags")
    * Application.tags  (related_name="nbtools_application_tags")

Because TaggableManager uses the shared extras.TaggedItem table, no
columns are added to the plugin tables themselves, but Django requires
the field declaration to be present in migration state.
"""

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0001_initial"),  # Ensure Tag & TaggedItem exist
        ("nbtools", "0004_update_service_and_application"),
    ]

    operations = [

        # -------------------------------------------------------------
        # Add tags to Service
        # -------------------------------------------------------------
        migrations.AddField(
            model_name="service",
            name="tags",
            field=taggit.managers.TaggableManager(
                to="extras.Tag",
                through="extras.TaggedItem",
                blank=True,
                related_name="nbtools_service_tags",
                help_text="Tags for this object.",
                verbose_name="Tags",
            ),
        ),

        # -------------------------------------------------------------
        # Add tags to Application
        # -------------------------------------------------------------
        migrations.AddField(
            model_name="application",
            name="tags",
            field=taggit.managers.TaggableManager(
                to="extras.Tag",
                through="extras.TaggedItem",
                blank=True,
                related_name="nbtools_application_tags",
                help_text="Tags for this object.",
                verbose_name="Tags",
            ),
        ),
    ]