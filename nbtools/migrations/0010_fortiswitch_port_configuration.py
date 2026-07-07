# Generated manually for nbtools

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("nbtools", "0009_fortisitebinding_comments_fix"),
    ]

    operations = [
        migrations.CreateModel(
            name="FortiSwitchPortConfiguration",
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
                    ),
                ),
                (
                    "last_updated",
                    models.DateTimeField(
                        auto_now=True,
                        null=True,
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
                    "name",
                    models.CharField(
                        help_text="Name of the predefined port configuration.",
                        max_length=100,
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "If disabled, this configuration cannot be selected "
                            "in the port tool."
                        ),
                    ),
                ),
                (
                    "native_vlan",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Forti native VLAN value, for example VLAN_10, "
                            "CLIENTS or 10."
                        ),
                        max_length=128,
                    ),
                ),
                (
                    "allowed_vlans",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            "List of Forti allowed VLAN values. "
                            "These should match the VLAN names/values returned by FortiGate."
                        ),
                    ),
                ),
                (
                    "apply_description",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "If enabled, this configuration also controls the "
                            "FortiSwitch port description. When enabled, Port "
                            "description is required."
                        ),
                    ),
                ),
                (
                    "match_description",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "If enabled, sync/readback matching also requires the "
                            "live FortiSwitch port description to match this configuration."
                        ),
                    ),
                ),
                (
                    "port_description",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Optional FortiSwitch port description. Required when "
                            "Apply description or Match description is enabled."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Administrative description of this predefined configuration.",
                    ),
                ),
                (
                    "comments",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Optional internal comments.",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Leave empty for a global configuration. Select a site "
                            "to make this configuration available only for that site."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fortiswitch_port_configurations",
                        to="dcim.site",
                    ),
                ),
            ],
            options={
                "verbose_name": "FortiSwitch port configuration",
                "verbose_name_plural": "FortiSwitch port configurations",
                "ordering": ["site__name", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="fortiswitchportconfiguration",
            constraint=models.UniqueConstraint(
                condition=models.Q(("site__isnull", True)),
                fields=("name",),
                name="nbtools_fsw_port_cfg_unique_global_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="fortiswitchportconfiguration",
            constraint=models.UniqueConstraint(
                condition=models.Q(("site__isnull", False)),
                fields=("site", "name"),
                name="nbtools_fsw_port_cfg_unique_site_name",
            ),
        ),
    ]
