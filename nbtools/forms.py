"""
forms.py

Forms for the NetBox Tools plugin: Application and Service models.

These use NetBoxModelForm so they integrate cleanly with NetBox 4.5's
generic ObjectEditView, tags, custom fields, and other model features.
"""

from netbox.forms import NetBoxModelForm
from tenancy.models import Contact

from .models import Application, Service


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