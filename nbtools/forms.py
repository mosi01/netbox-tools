"""
forms.py

Forms for the NetBox Tools plugin.

This file contains forms for:
- FortiSiteBinding
- Service
- Application

NetBox version reference:
- Compatible with NetBox 4.5.x / 4.6.x style plugin forms

Important
---------
For models inheriting from NetBoxModel, NetBox documents the use of
CommentField when exposing the built-in comments field in a model form.
This is the correct way to avoid NULL comments issues during object
creation/editing.
"""

from django import forms
from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField

from .models import Application, Service, FortiSiteBinding


class FortiSiteBindingForm(NetBoxModelForm):
    """
    Form for creating and editing FortiSiteBinding objects.

    Why comments is declared here
    -----------------------------
    FortiSiteBinding inherits from NetBoxModel. NetBox documents the use
    of CommentField on NetBoxModelForm when handling comments in object
    create/edit forms. This ensures the field is populated correctly and
    avoids NULL database inserts for the comments column.
    """

    # ------------------------------------------------------------------
    # NetBox-standard comments field
    # ------------------------------------------------------------------
    comments = CommentField(required=False)

    class Meta:
        model = FortiSiteBinding
        fields = (
            "site",
            "credential_alias",
            "enabled",
            "notes",
            "comments",
        )

    def clean(self):
        """
        Validate that the selected credential alias exists in
        PLUGINS_CONFIG['nbtools']['forti']['sites'].

        This keeps the database binding aligned with runtime plugin config.
        """
        cleaned_data = super().clean()

        alias = cleaned_data.get("credential_alias")

        from django.conf import settings

        config = settings.PLUGINS_CONFIG.get("nbtools", {}).get("forti", {})
        sites = config.get("sites", {})

        if alias and alias not in sites:
            raise forms.ValidationError(
                f"Alias '{alias}' does not exist in PLUGINS_CONFIG."
            )

        return cleaned_data


class ServiceForm(NetBoxModelForm):
    """
    Form for creating/editing Service objects.
    """

    class Meta:
        model = Service
        fields = (
            "name",
            "display_name",
            "description",
            "service_owner",
            "tags",
        )


class ApplicationForm(NetBoxModelForm):
    """
    Form for creating/editing Application objects.
    """

    class Meta:
        model = Application
        fields = (
            "name",
            "display_name",
            "status",
            "service",
            "application_owner",
            "technical_contact",
            "devices",
            "virtual_machines",
            "tags",
            "description",
        )
