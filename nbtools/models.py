from django.db import models
from dcim.models import Device
from virtualization.models import VirtualMachine
from tenancy.models import Contact


# SharePoint configuration model, used for SharePoint configuration
class SharePointConfig(models.Model):
    """
    Stores the connection details and mapping configuration
    for the SharePoint integration (site URL, OAuth client,
    folder mappings and file type mappings).
    """
    site_url = models.URLField()
    application_id = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)

    # Folder mappings: display name -> path/subfolder
    folder_mappings = models.JSONField(default=dict)

    # File type mappings: extension -> description
    file_type_mappings = models.JSONField(default=dict)

    def __str__(self):
        return f"SharePoint Config for {self.site_url}"


# Documentation Binding model, used for document caching
class DocumentationBinding(models.Model):
    """
    Caches discovered documentation items from SharePoint and
    links them logically to NetBox objects via server_name/
    application_name and category.
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
# New CMDB-style models: Service and Application
# ---------------------------------------------------------------------------

class Service(models.Model):
    """
    High-level business/IT service.

    This is intended to capture services such as "CRM", "Email Service",
    "FortiPAM Platform", etc., with an associated Service Owner contact.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (e.g. 'crm-core').",
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-friendly name (e.g. 'CRM Core Service').",
    )
    description = models.TextField(
        blank=True,
        help_text="Free-text description of what this service does.",
    )
    service_owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="owned_services",
        null=True,
        blank=True,
        help_text="Business/service owner contact.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        # Prefer the display name where present
        return self.display_name or self.name


class Application(models.Model):
    """
    Application running on top of the infrastructure.

    Applications can be linked to:
      * A parent Service
      * Application owner (contact)
      * Technical contact (contact)
      * Related Devices and/or Virtual Machines
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique internal name (e.g. 'crm-web').",
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-friendly name (e.g. 'CRM Web Frontend').",
    )
    status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status of the application (e.g. Production, Test).",
    )
    description = models.TextField(
        blank=True,
        help_text="Free-text description of this application.",
    )

    # Link to a Service
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        help_text="Parent service that this application is part of.",
    )

    # Contacts
    application_owner = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_applications",
        help_text="Business/application owner contact.",
    )
    technical_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technical_applications",
        help_text="Primary technical contact (engineer/SME).",
    )

    # Related infrastructure objects
    devices = models.ManyToManyField(
        Device,
        related_name="applications",
        blank=True,
        help_text="Devices related to this application.",
    )
    virtual_machines = models.ManyToManyField(
        VirtualMachine,
        related_name="applications",
        blank=True,
        help_text="Virtual machines related to this application.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        # Prefer the display name where present
        return self.display_name or self.name