"""
Application_list.py

NetBox Tools plugin - list view for Application objects.

This view uses NetBox's ObjectListView together with the ApplicationTable
and ApplicationFilterSet to render a Device-like list, including:
  - Header with title & action buttons (Add, Import, Export)
  - Quick search bar
  - Right-hand filters panel
  - Configure table button
  - Checkboxes for bulk actions
"""

import logging

from netbox.views.generic import ObjectListView

from ..models import Application
from ..tables import ApplicationTable
from ..filtersets import ApplicationFilterSet

logger = logging.getLogger("nbtools")


class ApplicationListView(ObjectListView):
    """
    List view for Applications.

    URL: /plugins/nbtools/applications/

    Uses NetBox's generic/object_list.html template to get the full
    standard UI look & feel.
    """

    queryset = Application.objects.all().prefetch_related(
        "service",
        "application_owner",
        "technical_contact",
        "devices",
        "virtual_machines",
    )
    table = ApplicationTable
    filterset = ApplicationFilterSet
    template_name = "generic/object_list.html"