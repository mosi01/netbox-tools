"""
models.py

Data models for the nbtools NetBox plugin.

This file contains:
- Existing SharePoint / documentation / service / application models
- NEW FortiSiteBinding model used for site -> FortiGate API resolution

Compatible with NetBox 4.5.0
"""

from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError

# NetBox base model
from netbox.models import NetBoxModel

# Existing NetBox models for relations
from dcim.models import Device, Site
from virtualization.models import VirtualMachine
from tenancy.models import Contact
from taggit.managers import TaggableManager


# ---------------------------------------------------------------------------
# SharePoint Config Model
# ---------------------------------------------------------------------------
class SharePointConfig(models.Model):
    """
    SharePoint configuration model used for storing SharePoint API
    credentials and folder/file type mappings.
    """

    site_url = models.URLField()
    application_id = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)

    # Folder mappings: display name/path configuration for SharePoint
    folder_mappings = models.JSONField(default=dict)

    # File type mappings: extension -> description
    file_type_mappings = models.JSONField(default=dict)

    def __str__(self):
        return f"SharePoint Config for {self.site_url}"


# ---------------------------------------------------------------------------
# Documentation Binding Model
# ---------------------------------------------------------------------------
class DocumentationBinding(models.Model):
    """
    Cached SharePoint document references, linked logically to NetBox
    objects via server_name / application_name and category.
    """

    category = models.CharField(max_length=255)
    server_name = models.CharField(max_length=255, db_index=True)
    application_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    file_type = models.CharField(max_length=50)
    sharepoint_url = models.TextField()

    def __str__(self):
        return f"{self.server_name} - {self.file_name} ({self.version})"


# ---------------------------------------------------------------------------
# Service model
# ---------------------------------------------------------------------------
class Service(NetBoxModel):
    """
    High-level business/IT service.

    NOTE:
    `tags` uses a unique related_name to avoid reverse accessor clashes.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (for example: crm-core).",
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-friendly display name.",
    )
    description = models.TextField(
        blank=True,
        help_text="Service description.",
    )
    service_owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="owned_services",
        null=True,
        blank=True,
        help_text="Business/service owner contact.",
    )

    tags = TaggableManager(
        to="extras.Tag",
        through="extras.TaggedItem",
        related_name="nbtools_service_tags",
        blank=True,
        help_text="Tags for this object.",
        verbose_name="Tags",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name


# ---------------------------------------------------------------------------
# Application model
# ---------------------------------------------------------------------------
class Application(NetBoxModel):
    """
    Application running on infrastructure components.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (for example: crm-web).",
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-friendly display name.",
    )
    status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status (for example: Production, Test).",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this application.",
    )

    # Link to parent Service
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        help_text="Parent service.",
    )

    # Contacts
    application_owner = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_applications",
        help_text="Business/application owner.",
    )
    technical_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technical_applications",
        help_text="Technical contact (SME).",
    )

    # Related infrastructure objects
    devices = models.ManyToManyField(
        Device,
        blank=True,
        related_name="applications",
        help_text="Devices related to this application.",
    )
    virtual_machines = models.ManyToManyField(
        VirtualMachine,
        blank=True,
        related_name="applications",
        help_text="Virtual machines related to this application.",
    )

    tags = TaggableManager(
        to="extras.Tag",
        through="extras.TaggedItem",
        related_name="nbtools_application_tags",
        blank=True,
        help_text="Tags for this object.",
        verbose_name="Tags",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name


# ---------------------------------------------------------------------------
# NEW: FortiSiteBinding
# ---------------------------------------------------------------------------

class FortiSiteBinding(NetBoxModel):

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name="forti_binding",
        help_text="NetBox site that should use a specific FortiGate alias.",
    )

    credential_alias = models.CharField(
        max_length=100,
        unique=True,
        help_text=(
            "Alias used to look up FortiGate connection settings in "
            "PLUGINS_CONFIG['nbtools']['forti']['sites']."
        ),
    )

    enabled = models.BooleanField(
        default=True,
        help_text="If disabled, Forti integration for this site is blocked.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional internal notes for this site binding.",
    )

    # ------------------------------------------------------------------
    # Explicit comments field
    # ------------------------------------------------------------------
    comments = models.TextField(
        blank=True,
        default="",
        help_text="Optional comments for this binding.",
    )

    class Meta:
        ordering = ["site__name"]
        permissions = [
            ("validate", "Validate FortiSwitch port settings"),
            ("sync", "Synchronise FortiSwitch port state"),
            ("deploy", "Deploy FortiSwitch port changes"),
        ]

    def __str__(self):
        return f"{self.site.name} -> {self.credential_alias}"

    def get_absolute_url(self):
        """
        Return the object detail URL.
        """
        return reverse("plugins:nbtools:fortisitebinding", args=[self.pk])

    def get_edit_url(self):
        """
        Return the object edit URL.
        """
        return reverse("plugins:nbtools:fortisitebinding_edit", args=[self.pk])

    def get_delete_url(self):
        """
        Return the object delete URL.
        """
        return reverse("plugins:nbtools:fortisitebinding_delete", args=[self.pk])


# ---------------------------------------------------------------------------
# FortiSwitch Port Configuration
# ---------------------------------------------------------------------------

class FortiSwitchPortConfiguration(NetBoxModel):
    """
    Predefined FortiSwitch port configuration profile.

    Scope
    -----
    - Global profile:
        site = None
        Available for all sites.

    - Site-specific profile:
        site = Site
        Available only for that site.

    Purpose
    -------
    This model stores reusable FortiSwitch port configurations that can be
    selected in the FortiSwitch Port Tool instead of manually entering Native
    VLAN, Allowed VLANs and optionally Description.

    The selected configuration should be converted by the view into the same
    desired_state structure as manual input:

        {
            "native_vlan": "...",
            "allowed_vlans": [...],
            "description": "..."
        }

    This means the existing validation, dry-run, payload generation and deploy
    logic can stay unchanged.
    """

    name = models.CharField(
        max_length=100,
        help_text="Name of the predefined port configuration.",
    )

    enabled = models.BooleanField(
        default=True,
        help_text="If disabled, this configuration cannot be selected in the port tool.",
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="fortiswitch_port_configurations",
        null=True,
        blank=True,
        help_text=(
            "Leave empty for a global configuration. "
            "Select a site to make this configuration available only for that site."
        ),
    )

    native_vlan = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Forti native VLAN value, for example VLAN_10, CLIENTS or 10.",
    )

    allowed_vlans = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of Forti allowed VLAN values. "
            "These should match the VLAN names/values returned by FortiGate."
        ),
    )

    apply_description = models.BooleanField(
        default=False,
        help_text=(
            "If enabled, this configuration also controls the FortiSwitch port description. "
            "When enabled, Port description is required."
        ),
    )

    match_description = models.BooleanField(
        default=False,
        help_text=(
            "If enabled, sync/readback matching also requires the live FortiSwitch "
            "port description to match this configuration."
        ),
    )

    port_description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Optional FortiSwitch port description. "
            "Required when Apply description or Match description is enabled."
        ),
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Administrative description of this predefined configuration.",
    )

    comments = models.TextField(
        blank=True,
        default="",
        help_text="Optional internal comments.",
    )

    class Meta:
        ordering = ["site__name", "name"]
        verbose_name = "FortiSwitch port configuration"
        verbose_name_plural = "FortiSwitch port configurations"

        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(site__isnull=True),
                name="nbtools_fsw_port_cfg_unique_global_name",
            ),
            models.UniqueConstraint(
                fields=["site", "name"],
                condition=models.Q(site__isnull=False),
                name="nbtools_fsw_port_cfg_unique_site_name",
            ),
        ]

    def __str__(self):
        if self.site:
            return f"{self.name} ({self.site.name})"
        return f"{self.name} (Global)"

    def clean(self):
        """
        Validate and normalise the configuration.

        Rules
        -----
        - Allowed VLANs must be a list.
        - Empty VLAN values are removed.
        - Native VLAN is normalised to a stripped string.
        - Port description is required if Apply description is enabled.
        - Port description is also required if Match description is enabled.
        """

        super().clean()

        if self.allowed_vlans is None:
            self.allowed_vlans = []

        if not isinstance(self.allowed_vlans, list):
            raise ValidationError({
                "allowed_vlans": "Allowed VLANs must be stored as a list."
            })

        cleaned_allowed_vlans = []

        for vlan in self.allowed_vlans:
            if vlan in (None, ""):
                continue

            cleaned_value = str(vlan).strip()

            if cleaned_value:
                cleaned_allowed_vlans.append(cleaned_value)

        self.allowed_vlans = cleaned_allowed_vlans

        if self.native_vlan:
            self.native_vlan = str(self.native_vlan).strip()

        if self.port_description:
            self.port_description = str(self.port_description).strip()

        if self.apply_description and not self.port_description:
            raise ValidationError({
                "port_description": (
                    "Port description is required when Apply description is enabled."
                )
            })

        if self.match_description and not self.port_description:
            raise ValidationError({
                "port_description": (
                    "Port description is required when Match description is enabled."
                )
            })

    
    def get_absolute_url(self):
        return reverse(
            "plugins:nbtools:fortiswitchportconfiguration",
            args=[self.pk],
        )


    def get_edit_url(self):
        return reverse(
            "plugins:nbtools:fortiswitchportconfiguration",
            args=[self.pk],
        )

    def get_delete_url(self):
        return reverse(
            "plugins:nbtools:fortiswitchportconfiguration",
            args=[self.pk],
        )
