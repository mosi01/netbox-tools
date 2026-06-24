"""
forms.py

Forms for the NetBox Tools plugin: Application and Service models.

These use NetBoxModelForm so they integrate cleanly with NetBox 4.5's
generic ObjectEditView, tags, custom fields, and other model features.
"""
from django import forms
from netbox.forms import NetBoxModelForm
from tenancy.models import Contact

from .models import Application, Service, FortiSiteBinding



class FortiSiteBindingForm(NetBoxModelForm):
    """
    Form for creating/updating Forti site bindings.
    """

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
        Validate alias exists in PLUGINS_CONFIG
        """
        super().clean()

        alias = self.cleaned_data.get("credential_alias")

        from django.conf import settings

        config = settings.PLUGINS_CONFIG.get("nbtools", {}).get("forti", {})
        sites = config.get("sites", {})

        if alias not in sites:
            raise forms.ValidationError(
                f"Alias '{alias}' does not exist in PLUGINS_CONFIG."
            )

        return self.cleaned_data



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
