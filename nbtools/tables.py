"""
tables.py

NetBox Tools plugin - table definitions for Service and Application models.

These tables integrate with NetBox's generic ObjectListView to render
Device-like list pages, including:

  * Checkbox column (provided by NetBoxTable)
  * Sortable columns
  * Configure table support
  * Integration with filtersets and table configs

NetBox version target: 4.5.0
"""

import django_tables2 as tables

from netbox.tables import NetBoxTable

from .models import Service, Application


class ServiceTable(NetBoxTable):
    """
    Table for listing Service objects.

    Columns:
      - Name (link to detail view)
      - Display name
      - Service owner
      - Description (hidden by default)
      - Application count (how many applications belong to this service)
    """

    # Name column, link to the Service detail view
    name = tables.Column(
        linkify=True,
        verbose_name="Name",
    )

    display_name = tables.Column(
        verbose_name="Display Name",
    )

    service_owner = tables.Column(
        verbose_name="Service Owner",
    )

    application_count = tables.Column(
        verbose_name="Applications",
        accessor="applications.count",
    )

    class Meta(NetBoxTable.Meta):
        """
        NetBoxTable.Meta gives us:

          * A checkbox column bound to "pk"
          * Support for table configs
          * Default styling

        We only need to specify which fields are available and which are
        shown by default.
        """
        model = Service
        fields = (
            "pk",               # Required for the checkbox column
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
      - Description (hidden by default)
    """

    # Name column, link to the Application detail view
    name = tables.Column(
        linkify=True,
        verbose_name="Name",
    )

    display_name = tables.Column(
        verbose_name="Display Name",
    )

    status = tables.Column(
        verbose_name="Status",
    )

    service = tables.Column(
        verbose_name="Service",
        linkify=True,
    )

    application_owner = tables.Column(
        verbose_name="Application Owner",
    )

    technical_contact = tables.Column(
        verbose_name="Technical Contact",
    )

    device_count = tables.Column(
        verbose_name="Devices",
        accessor="devices.count",
    )

    vm_count = tables.Column(
        verbose_name="Virtual Machines",
        accessor="virtual_machines.count",
    )

    class Meta(NetBoxTable.Meta):
        """
        Table configuration for the Application model.
        """
        model = Application
        fields = (
            "pk",               # Required for the checkbox column
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