"""
forms.py

Forms for the NetBox Tools plugin.

This file contains forms for:
- FortiSiteBinding
- Service
- Application

NetBox reference
----------------
- Uses NetBoxModelForm, which is the documented base form class for
  creating and editing NetBox models in plugins.
- Uses CommentField for the built-in comments field, as documented by
  NetBox for plugin model forms.

Compatible with NetBox 4.5.x / 4.6.x style plugin forms.
"""

from django import forms
from django.conf import settings

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField

from .models import Application, Service, FortiSiteBinding


class FortiSiteBindingForm(NetBoxModelForm):
    """
    Form for creating and editing FortiSiteBinding objects.

    Why this form includes CommentField
    -----------------------------------
    NetBox documents the use of CommentField for comments on plugin model
    forms based on NetBoxModel. This is the correct pattern for handling
    comments in create/edit forms. [1](https://docs.python.org/3/library/ipaddress.html)
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

        Important:
        - Call super().clean() to populate self.cleaned_data
        - Use self.cleaned_data directly
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
        Save the FortiSiteBinding while guaranteeing that comments is never NULL.

        Why this is necessary
        ---------------------
        Your traceback shows inserts are still reaching PostgreSQL with
        comments = NULL. To prevent that reliably, always set the instance
        field directly from cleaned_data and coerce empty input to "" before
        saving.
        """
        instance = super().save(commit=False)

        # --------------------------------------------------------------
        # Critical fix:
        # Always drive the model value from the submitted form value.
        # If comments is empty or missing, force an empty string rather
        # than letting NULL reach the database.
        # --------------------------------------------------------------
        instance.comments = self.cleaned_data.get("comments") or ""

        if commit:
            instance.save()

            # Save many-to-many relations if present
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
