"""
models.py

Extended data models for nbtools plugin.

This file includes:
- Existing models (unchanged)
- NEW FortiSwitch / FortiGate integration models

Compatible with NetBox 4.5.0
"""

from django.db import models

# NetBox imports
from netbox.models import NetBoxModel

# Existing NetBox models for relations
from dcim.models import Device, Interface, Site
from virtualization.models import VirtualMachine
from tenancy.models import Contact
from taggit.managers import TaggableManager

# ---------------------------------------------------------------------------
# SharePoint Config Model (UNCHANGED)
# ---------------------------------------------------------------------------
class SharePointConfig(models.Model):
    """
    SharePoint configuration model used for storing API credentials.
    """

    site_url = models.URLField()
    application_id = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)

    folder_mappings = models.JSONField(default=dict)
    file_type_mappings = models.JSONField(default=dict)

    def __str__(self):
        return f"SharePoint Config for {self.site_url}"


# ---------------------------------------------------------------------------
# Documentation Binding Model (UNCHANGED)
# ---------------------------------------------------------------------------
class DocumentationBinding(models.Model):
    """
    Cached SharePoint documents linked to NetBox objects.
    """

    category = models.CharField(max_length=255)
    server_name = models.CharField(max_length=255, db_index=True)
    application_name = models.CharField(max_length=255, null=True, blank=True)

    file_name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    file_type = models.CharField(max_length=50)
    sharepoint_url = models.TextField()

    def __str__(self):
        return f"{self.server_name} - {self.file_name} ({self.version})"


# ---------------------------------------------------------------------------
# Service model (UNCHANGED)
# ---------------------------------------------------------------------------
class Service(NetBoxModel):
    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    service_owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="owned_services",
        null=True,
        blank=True,
    )

    tags = TaggableManager(
        to="extras.Tag",
        through="extras.TaggedItem",
        related_name="nbtools_service_tags",
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name


# ---------------------------------------------------------------------------
# Application model (UNCHANGED)
# ---------------------------------------------------------------------------
class Application(NetBoxModel):
    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )

    application_owner = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_applications",
    )

    technical_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technical_applications",
    )

    devices = models.ManyToManyField(Device, blank=True, related_name="applications")

    virtual_machines = models.ManyToManyField(
        VirtualMachine,
        blank=True,
        related_name="applications",
    )

    tags = TaggableManager(
        to="extras.Tag",
        through="extras.TaggedItem",
        related_name="nbtools_application_tags",
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name


# ===========================================================================
# ======================= FORTINET INTEGRATION ===============================
# ===========================================================================

# ---------------------------------------------------------------------------
# FortiGate Site Binding
# ---------------------------------------------------------------------------
class FortiSiteBinding(NetBoxModel):
    """
    Maps a NetBox Site to a FortiGate (FortiLink controller).

    NOTE:
    - No secrets stored here
    - Credentials resolved via PLUGINS_CONFIG
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name="forti_binding",
    )

    fortigate_host = models.CharField(
        max_length=255,
        help_text="Hostname or IP of FortiGate",
    )

    vdom = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional VDOM",
    )

    credential_alias = models.CharField(
        max_length=100,
        help_text="Key used in PLUGINS_CONFIG",
    )

    verify_ssl = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.site.name} -> {self.fortigate_host}"


# ---------------------------------------------------------------------------
# Forti Port Profile
# ---------------------------------------------------------------------------
class FortiPortProfile(NetBoxModel):
    """
    Defines reusable port configuration templates.
    """

    name = models.CharField(max_length=255)
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="forti_profiles",
    )

    MODE_CHOICES = [
        ("access", "Access"),
        ("trunk", "Trunk"),
    ]

    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    native_vlan = models.IntegerField(null=True, blank=True)

    allowed_vlans = models.JSONField(
        default=list,
        help_text="List of allowed VLAN IDs",
    )

    description = models.CharField(max_length=255, blank=True)

    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("name", "site")

    def __str__(self):
        return f"{self.name} ({self.site.name})"


# ---------------------------------------------------------------------------
# Forti Port Intent (CORE MODEL)
# ---------------------------------------------------------------------------
class FortiPortIntent(NetBoxModel):
    """
    Desired state for a specific interface.
    """

    interface = models.OneToOneField(
        Interface,
        on_delete=models.CASCADE,
        related_name="forti_intent",
    )

    profile = models.ForeignKey(
        FortiPortProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Desired state overrides
    desired_mode = models.CharField(max_length=20, blank=True)
    desired_native_vlan = models.IntegerField(null=True, blank=True)
    desired_allowed_vlans = models.JSONField(default=list)

    managed = models.BooleanField(default=True)

    # Safety flags
    is_uplink = models.BooleanField(
        default=False,
        help_text="If true, port cannot be modified",
    )

    # Last sync / deploy state
    last_live_state = models.JSONField(default=dict, blank=True)
    last_sync_time = models.DateTimeField(null=True, blank=True)

    last_deploy_status = models.CharField(max_length=50, blank=True)
    last_validation_status = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.interface.device.name}:{self.interface.name}"


# ---------------------------------------------------------------------------
# Forti Port Operation Log
# ---------------------------------------------------------------------------
class FortiPortOperation(NetBoxModel):
    """
    Tracks validation, dry-run, deploy and sync operations.
    """

    OPERATION_CHOICES = [
        ("validate", "Validate"),
        ("dry_run", "Dry Run"),
        ("deploy", "Deploy"),
        ("sync", "Sync"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    interface = models.ForeignKey(Interface, on_delete=models.CASCADE)

    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    requested_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
    )

    dry_run = models.BooleanField(default=False)

    result_log = models.TextField(blank=True)

    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)

    warnings = models.JSONField(default=list)

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.interface} - {self.operation} ({self.status})"
