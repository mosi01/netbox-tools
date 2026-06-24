"""
models.py

Data models for the nbtools NetBox plugin.

This file contains:
- Existing SharePoint / documentation / service / application models
- NEW FortiSiteBinding model used for site -> FortiGate API resolution

Compatible with NetBox 4.5.0
"""

from django.db import models

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
    """
    Bind a NetBox site to a FortiGate connection alias.

    Runtime FortiGate credentials should live in PLUGINS_CONFIG.
    This model only stores the relationship:
        NetBox Site -> credential_alias
    """

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

    class Meta:
        ordering = ["site__name"]
        permissions = [
            ("validate", "Validate FortiSwitch port settings"),
            ("sync", "Synchronise FortiSwitch port state"),
            ("deploy", "Deploy FortiSwitch port changes"),
        ]

    def __str__(self):
        return f"{self.site.name} -> {self.credential_alias}"

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------
    def get_absolute_url(self):
        """
        Return the plugin object detail URL.
        """
        return reverse("plugins:nbtools:fortisitebinding", args=[self.pk])

    def get_edit_url(self):
        """
        Return the plugin object edit URL.
        """
        return reverse("plugins:nbtools:fortisitebinding_edit", args=[self.pk])

    def get_delete_url(self):
        """
        Return the plugin object delete URL.
        """
        return reverse("plugins:nbtools:fortisitebinding_delete", args=[self.pk])

