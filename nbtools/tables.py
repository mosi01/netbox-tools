"""
tables.py

NetBox Tools plugin - table definitions for Application and Service models.

These tables are used by NetBox's generic ObjectListView to render
Device-like list pages, with checkboxes, sortable columns, and
Configure table support.
"""

from netbox.tables import NetBoxTable, columns

from .models import Application, Service


class ServiceTable(NetBoxTable):
    """
    Table for listing Service objects.

    Columns:
      - Name (link to detail view)
      - Display name
      - Service owner
      - Description
      - Application count (how many applications belong to this service)
      - Checkbox (for bulk actions)
    """

    name = columns.Column(
        linkify=True,
        verbose_name="Name",
    )

    display_name = columns.Column(
        verbose_name="Display Name",
    )

    service_owner = columns.Column(
        verbose_name="Service Owner",
    )

    application_count = columns.Column(
        verbose_name="Applications",
        accessor="applications.count",
    )

    class Meta(NetBoxTable.Meta):
        model = Service
        fields = (
            "pk",
            "name",
            "display_name",
            "service_owner",
            "application_count",
            "description",
        )
        default_columns = (
            "name",
            "display_name",
            "service_owner",
            "application_count",
        )


class ApplicationTable(NetBoxTable):
    """
    Table for listing Application objects.

    Columns:
      - Name (link to detail view)
      - Display name
      - Status
      - Service
      - Application owner
      - Technical contact
      - Count of related Devices
      - Count of related Virtual Machines
      - Checkbox (for bulk actions)
    """

    name = columns.Column(
        linkify=True,
        verbose_name="Name",
    )

    display_name = columns.Column(
        verbose_name="Display Name",
    )

    status = columns.Column(
        verbose_name="Status",
    )

    service = columns.Column(
        verbose_name="Service",
        linkify=True,
    )

    application_owner = columns.Column(
        verbose_name="Application Owner",
    )

    technical_contact = columns.Column(
        verbose_name="Technical Contact",
    )

    device_count = columns.Column(
        verbose_name="Devices",
        accessor="devices.count",
    )

    vm_count = columns.Column(
        verbose_name="Virtual Machines",
        accessor="virtual_machines.count",
    )

    class Meta(NetBoxTable.Meta):
        model = Application
        fields = (
            "pk",
            "name",
            "display_name",
            "status",
            "service",
            "application_owner",
            "technical_contact",
            "device_count",
            "vm_count",
            "description",
        )
        default_columns = (
            "name",
            "display_name",
            "status",
            "service",
            "application_owner",
            "technical_contact",
            "device_count",
            "vm_count",
        )