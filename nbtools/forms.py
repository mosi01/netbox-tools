"""
forms.py

Forms for 4.5.x / 4.6.x style plugin forms.Forms for the NetBox Tools plugin.
"""

from django import forms
from django.conf import settings

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField

from .models import Application, Service, FortiSiteBinding, FortiSwitchPortConfiguration


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



class FortiSwitchPortConfigurationForm(forms.ModelForm):
    """
    Administration form for predefined FortiSwitch port configurations.

    The allowed_vlans_text field makes it easier to manage VLANs in the UI
    while still storing them as a JSON list in the database.
    """

    allowed_vlans_text = forms.CharField(
        required=False,
        label="Allowed VLANs",
        help_text="Enter one VLAN per line, or comma-separated.",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    class Meta:
        model = FortiSwitchPortConfiguration
        fields = (
            "name",
            "enabled",
            "site",
            "native_vlan",
            "allowed_vlans_text",
            "apply_description",
            "port_description",
            "match_description",
            "description",
            "comments",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        
        # Only allow sites that exist in FortiSiteBinding
        bound_sites = FortiSiteBinding.objects.values_list("site_id", flat=True)

        self.fields["site"].queryset = Site.objects.filter(
            id__in=bound_sites
        )

        
        instance = self.instance
        if instance and instance.pk:
            self.fields["allowed_vlans_text"].initial = "\n".join(
                instance.allowed_vlans or []
            )

    def clean_allowed_vlans_text(self):
        raw_value = self.cleaned_data.get("allowed_vlans_text") or ""

        values = []
        for line in raw_value.replace(",", "\n").splitlines():
            value = line.strip()
            if value:
                values.append(value)

        return values

    def clean(self):
        cleaned_data = super().clean()

        apply_description = cleaned_data.get("apply_description")
        match_description = cleaned_data.get("match_description")
        port_description = cleaned_data.get("port_description")

        if port_description:
            port_description = str(port_description).strip()

        if apply_description and not port_description:
            self.add_error(
                "port_description",
                "Port description is required when Apply description is enabled.",
            )

        if match_description and not port_description:
            self.add_error(
                "port_description",
                "Port description is required when Match description is enabled.",
            )

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.allowed_vlans = self.cleaned_data.get("allowed_vlans_text") or []

        if commit:
            instance.save()
            self.save_m2m()

        return instance

