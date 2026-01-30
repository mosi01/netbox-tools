"""
Django migration to add Service and Application models to the nbtools plugin.

This migration assumes that:
  * The app label is "nbtools"
  * An initial migration already exists (e.g. 0001_initial) which creates
    SharePointConfig and DocumentationBinding.

If your existing migration name is different, update the dependency in the
Migration class below.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    # NOTE:
    # If your existing initial migration is not named "0001_initial",
    # adjust this dependency to match the last migration file.
    dependencies = [
        ("tenancy", "0001_initial"),        # for Contact model
        ("dcim", "0001_initial"),           # for Device model
        ("virtualization", "0001_initial"), # for VirtualMachine model
        ("nbtools", "0001_initial"),        # your plugin's initial migration
        ("nbtools", "0002_add_file_type_mappings")
    ]

    operations = [
        # ---------------------------------------------------------------------
        # Create Service model
        # ---------------------------------------------------------------------
        migrations.CreateModel(
            name="Service",
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
                    "name",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        help_text="Unique internal name (e.g. 'crm-core').",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        max_length=255,
                        help_text="Human-friendly name (e.g. 'CRM Core Service').",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Free-text description of what this service does."
                        ),
                    ),
                ),
                (
                    "service_owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_services",
                        to="tenancy.contact",
                        null=True,
                        blank=True,
                        help_text="Business/service owner contact.",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),

        # ---------------------------------------------------------------------
        # Create Application model
        # ---------------------------------------------------------------------
        migrations.CreateModel(
            name="Application",
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
                    "name",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        help_text="Unique internal name (e.g. 'crm-web').",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        max_length=255,
                        help_text="Human-friendly name (e.g. 'CRM Web Frontend').",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=50,
                        blank=True,
                        help_text="Status of the application (e.g. Production, Test).",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Free-text description of this application.",
                    ),
                ),
                # ForeignKey to Service
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="applications",
                        to="nbtools.service",
                        null=True,
                        blank=True,
                        help_text="Parent service that this application is part of.",
                    ),
                ),
                # Application owner contact
                (
                    "application_owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_applications",
                        to="tenancy.contact",
                        null=True,
                        blank=True,
                        help_text="Business/application owner contact.",
                    ),
                ),
                # Technical contact
                (
                    "technical_contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="technical_applications",
                        to="tenancy.contact",
                        null=True,
                        blank=True,
                        help_text="Primary technical contact (engineer/SME).",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),

        # ---------------------------------------------------------------------
        # Add ManyToMany fields on Application (Devices / VirtualMachines)
        # ---------------------------------------------------------------------
        migrations.AddField(
            model_name="application",
            name="devices",
            field=models.ManyToManyField(
                blank=True,
                help_text="Devices related to this application.",
                related_name="applications",
                to="dcim.device",
            ),
        ),
        migrations.AddField(
            model_name="application",
            name="virtual_machines",
            field=models.ManyToManyField(
                blank=True,
                help_text="Virtual machines related to this application.",
                related_name="applications",
                to="virtualization.virtualmachine",
            ),
        ),
    ]