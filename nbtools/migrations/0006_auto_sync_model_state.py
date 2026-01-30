"""
Migration 0006_auto_sync_model_state

This migration synchronizes the model options for the Service and
Application models with the current definitions in models.py.

In particular, it ensures that the `ordering` option for both models
matches the Meta configuration:

    class Service(NetBoxModel):
        class Meta:
            ordering = ["name"]

    class Application(NetBoxModel):
        class Meta:
            ordering = ["name"]

This migration does not alter any database columns: It only updates
the model state recorded in Django's migration history so that the
current models.py and the migration state are consistent and Django
stops reporting "models have changes not yet reflected in migrations"
for the nbtools app.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nbtools", "0005_add_tag_fields"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="service",
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AlterModelOptions(
            name="application",
            options={
                "ordering": ["name"],
            },
        ),
    ]