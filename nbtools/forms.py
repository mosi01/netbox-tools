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
      built-in comments field in a model form.
    - The comments field should be included on the form; NetBox notes
      that comment fields render last automatically. [1](https://netbox.readthedocs.io/en/stable/plugins/development/forms/)
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

        FIX:
        - super().clean() may return None in this execution path, so
          always coerce to an empty dict before using .get().
        """
        cleaned_data = super().clean() or {}

        alias = cleaned_data.get("credential_alias")

        from django.conf import settings

        plugin_config = settings.PLUGINS_CONFIG.get("nbtools", {}) or {}
        forti_config = plugin_config.get("forti", {}) or {}
        sites = forti_config.get("sites", {}) or {}

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
``
