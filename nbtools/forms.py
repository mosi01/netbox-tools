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

    Notes
    -----
    - FortiSiteBinding inherits from NetBoxModel.
    - NetBox documents the use of CommentField when handling the
      built-in comments field in a model form. [1](https://docs.python.org/3/library/ipaddress.html)
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

        IMPORTANT
        ---------
        Do not assign the return value of super().clean() directly and
        rely on that object. Django/NetBox populates self.cleaned_data.
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
        Save the FortiSiteBinding while ensuring comments is never NULL.

        Why this is needed
        ------------------
        Even though the form exposes a CommentField, an empty submission can
        still resolve to None in practice. The database column for comments on
        a NetBoxModel-backed object is not nullable in your current schema, so
        we must normalise None -> "" before saving.
        """
        instance = super().save(commit=False)

        # Normalize comments so PostgreSQL never receives NULL
        if getattr(instance, "comments", None) is None:
            instance.comments = ""

        if commit:
            instance.save()

            # Save many-to-many data if present (safe practice for ModelForms)
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
