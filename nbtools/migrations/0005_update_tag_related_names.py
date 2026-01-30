"""
Migration 0005_update_tag_related_names

This migration updates the tag field definitions for the Service and
Application models. Both models now explicitly override the TaggableManager
in order to provide unique related_name values:

    * Service.tags     -> related_name = "nbtools_service_tags"
    * Application.tags -> related_name = "nbtools_application_tags"

Because TaggableManager is a many‑to‑many‑like descriptor backed by the
shared extras.TaggedItem table, no columns are created on the plugin’s
own tables. However, Django still requires an AlterField migration so that
the ORM state matches the Python model definitions.
"""

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0001_initial"),  # ensure Tag & TaggedItem exist
        ("nbtools", "0004_update_service_and_application"),
    ]

    operations = [

        # ------------------------------------------------------------------
        # Update Service.tags to use the new related_name
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="service",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="Tags for this object.",
                through="extras.TaggedItem",
                to="extras.Tag",
                related_name="nbtools_service_tags",
                verbose_name="Tags",
            ),
        ),

        # ------------------------------------------------------------------
        # Update Application.tags to use its new related_name
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="application",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="Tags for this object.",
                through="extras.TaggedItem",
                to="extras.Tag",
                related_name="nbtools_application_tags",
                verbose_name="Tags",
            ),
        ),
    ]