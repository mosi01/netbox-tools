"""
Migration 0005_fix_tag_related_names

Fixes tag reverse accessor collisions by adding unique related_name values
to the TaggableManager fields on Service and Application models.
"""

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ("nbtools", "0004_update_service_and_application"),
    ]

    operations = [

        # ------------------------------------------------------------------
        # Update Service.tags related_name
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="service",
            name="tags",
            field=taggit.managers.TaggableManager(
                related_name="nbtools_service_tags",
                to="extras.Tag",
                through="extras.TaggedItem",
                blank=True,
                help_text="Tags for this object",
                verbose_name="Tags",
            ),
        ),

        # ------------------------------------------------------------------
        # Update Application.tags related_name
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="application",
            name="tags",
            field=taggit.managers.TaggableManager(
                related_name="nbtools_application_tags",
                to="extras.Tag",
                through="extras.TaggedItem",
                blank=True,
                help_text="Tags for this object",
                verbose_name="Tags",
            ),
        ),
    ]