"""
0007_sync_service_application_fields
====================================

This migration synchronizes the field definitions for the Service and
Application models with their current definitions in models.py.

It is intended to resolve Django's warning that models in the 'nbtools'
app have changes not yet reflected in migrations, by explicitly
declaring the current field options (help_text, blank/null, etc.)
within the migration state.

NOTE:
This migration does NOT change the actual database schema in a
meaningful way: It re-declares existing fields with their current
attributes, making it effectively a no-op at the database level, while
allowing Django's migration autodetector to see the model state as
fully up-to-date.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nbtools", "0006_auto_sync_model_state"),
    ]

    operations = [
        # ------------------------------------------------------------------
        # Service fields
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="service",
            name="name",
            field=models.CharField(
                max_length=255,
                unique=True,
                help_text="Unique internal name (e.g. 'crm-core').",
            ),
        ),
        migrations.AlterField(
            model_name="service",
            name="display_name",
            field=models.CharField(
                max_length=255,
                help_text="Human-friendly display name.",
            ),
        ),
        migrations.AlterField(
            model_name="service",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Service description.",
            ),
        ),
        migrations.AlterField(
            model_name="service",
            name="service_owner",
            field=models.ForeignKey(
                to="tenancy.Contact",
                on_delete=models.PROTECT,
                related_name="owned_services",
                null=True,
                blank=True,
                help_text="Business/service owner contact.",
            ),
        ),

        # ------------------------------------------------------------------
        # Application fields
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="application",
            name="name",
            field=models.CharField(
                max_length=255,
                unique=True,
                help_text="Unique internal name (e.g. 'crm-web').",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="display_name",
            field=models.CharField(
                max_length=255,
                help_text="Human-friendly display name.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="status",
            field=models.CharField(
                max_length=50,
                blank=True,
                help_text="Status (e.g. Production, Test).",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Description of this application.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="service",
            field=models.ForeignKey(
                to="nbtools.Service",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="applications",
                help_text="Parent service.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="application_owner",
            field=models.ForeignKey(
                to="tenancy.Contact",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="owned_applications",
                help_text="Business/application owner.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="technical_contact",
            field=models.ForeignKey(
                to="tenancy.Contact",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="technical_applications",
                help_text="Technical contact (SME).",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="devices",
            field=models.ManyToManyField(
                to="dcim.Device",
                blank=True,
                related_name="applications",
                help_text="Devices related to this application.",
            ),
        ),
        migrations.AlterField(
            model_name="application",
            name="virtual_machines",
            field=models.ManyToManyField(
                to="virtualization.VirtualMachine",
                blank=True,
                related_name="applications",
                help_text="Virtual machines related to this application.",
            ),
        ),
    ]