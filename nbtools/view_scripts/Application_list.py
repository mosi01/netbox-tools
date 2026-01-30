"""
Application_list.py

NetBox Tools plugin - list view for Application objects.

Uses NetBox's ObjectListView together with ApplicationTable and
ApplicationFilterSet to render a Device-like list:

  * Header with title & action buttons
  * Quick search bar
  * Right-hand filters panel
  * Configure table button
  * Checkboxes for bulk actions
"""

import logging

from django.urls import reverse

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

    The Add button is wired explicitly to the plugin's Application
    creation view via get_extra_context().
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

    def get_extra_context(self, request):
        """
        Inject the correct Add URL for Applications so the "Add" button
        on the list page points to our plugin's creation view, rather
        than rendering as 'None'.
        """
        context = super().get_extra_context(request)
        context["add_url"] = reverse("plugins:nbtools:application_add")
        return context