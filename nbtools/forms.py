"""
forms.py

Forms for 4.5.x / 4.6.x style plugin forms.Forms for the NetBox Tools plugin.
"""

from django import forms
from django.conf import settings

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField

from .models import Application, Service, FortiSiteBinding


class FortiSiteBindingForm(NetBoxModelForm):
    """
    Form for creating and editing FortiSiteBinding objects.
    """

    # NetBox-style comment field for the comments model field
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
        """
        super().clean()

        alias = self.cleaned_data.get("credential_alias")

        plugin_config = settings.PLUGINS_CONFIG.get("nbtools", {}) or {}
        forti_config = plugin_config.get("forti", {}) or {}
        sites = forti_config.get("sites", {}) or {}

        if alias and alias not in sites:
            raise forms.ValidationError(
                f"Alias '{alias}' does not exist in PLUGINS_CONFIG."
            )

        return self.cleaned_data

    def save(self, commit=True):
        """
        Save the FortiSiteBinding while ensuring comments is always a
        non-null string before the object is written to the database.
        """
        instance = super().save(commit=False)

        # Force comments to a concrete string value
        instance.comments = self.cleaned_data.get("comments") or ""

        if commit:
            instance.save()

            # Save any many-to-many data if present
            if hasattr(self, "save_m2m"):
                self.save_m2m()

        return instance


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

This file contains forms for:
- FortiSiteBinding
- Service
- Application

