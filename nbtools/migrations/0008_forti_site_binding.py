from django.db import migrations, models
import django.db.models.deletion
import taggit.managers


class Migration(migrations.Migration):
    """
    Migration to create the FortiSiteBinding database table.
    """

    # ------------------------------------------------------------------
    # Adjust dependencies to match your existing migration chain.
    #
    # If you already have an existing migration, replace
    # "0001_initial" below with your actual latest migration filename
    # without the ".py" extension.
    # ------------------------------------------------------------------
    dependencies = [
        ("nbtools", "0007_initial"),      # CHANGE this if your latest nbtools migration is different
    ]

    operations = [
        migrations.CreateModel(
            name="FortiSiteBinding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "last_updated",
                    models.DateTimeField(
                        auto_now=True,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "comments",
                    models.TextField(
                        blank=True,
                    ),
                ),
                (
                    "credential_alias",
                    models.CharField(
                        help_text=(
                            "Alias used to look up FortiGate connection settings in "
                            "PLUGINS_CONFIG['nbtools']['forti']['sites']."
                        ),
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text="If disabled, Forti integration for this site is blocked.",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Optional internal notes for this site binding.",
                    ),
                ),
                (
                    "site",
                    models.OneToOneField(
                        help_text="NetBox site that should use a specific FortiGate alias.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forti_binding",
                        to="dcim.site",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        blank=True,
                        through="extras.TaggedItem",
                        to="extras.Tag",
                        verbose_name="Tags",
                    ),
                ),
            ],
            options={
                "ordering": ["site__name"],
                "permissions": [
                    ("validate", "Validate FortiSwitch port settings"),
                    ("sync", "Synchronise FortiSwitch port state"),
                    ("deploy", "Deploy FortiSwitch port changes"),
                ],
            },
        ),
    ]

