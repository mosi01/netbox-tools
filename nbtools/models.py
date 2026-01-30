from django.db import models

# NetBox imports
from netbox.models import NetBoxModel

# Existing NetBox models for relations
from dcim.models import Device
from virtualization.models import VirtualMachine
from tenancy.models import Contact
from taggit.managers import TaggableManager


# ---------------------------------------------------------------------------
# SharePoint Config Model (unchanged)
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
# Documentation Binding Model (unchanged)
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
# NEW MODELS — Service and Application (NetBoxModel-based)
# ---------------------------------------------------------------------------
class Service(NetBoxModel):
    """
    High-level business/IT service.

    NOTE:
    We explicitly define the `tags` field with a unique related_name
    to avoid clashing with the core ipam.Service.tags reverse accessor.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (e.g. 'crm-core').",
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

    # IMPORTANT: Override tags to avoid conflict with ipam.Service.tags
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


class Application(NetBoxModel):
    """
    Application running on infrastructure components.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (e.g. 'crm-web').",
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-friendly display name.",
    )
    status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status (e.g. Production, Test).",
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

    # Optional: give Application its own unique tag reverse accessor too
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