"""
Service_list.py

NetBox Tools plugin - list view for Service objects.

Uses NetBox's ObjectListView together with ServiceTable and
ServiceFilterSet to render a Device-like list.
"""

import logging

from django.urls import reverse

from netbox.views.generic import ObjectListView

from ..models import Service
from ..tables import ServiceTable
from ..filtersets import ServiceFilterSet

logger = logging.getLogger("nbtools")


class ServiceListView(ObjectListView):
    """
    List view for Services.

    URL: /plugins/nbtools/services/

    Uses NetBox's generic/object_list.html template to get the full
    standard UI.

    The Add button is wired explicitly to the plugin's Service creation
    view via get_extra_context().
    """

    queryset = Service.objects.all().prefetch_related("service_owner")
    table = ServiceTable
    filterset = ServiceFilterSet
    template_name = "generic/object_list.html"

    def get_extra_context(self, request):
        """
        Inject the correct Add URL for Services so the "Add" button on
        the list page points to our plugin's creation view.
        """
        context = super().get_extra_context(request)
        context["add_url"] = reverse("plugins:nbtools:service_add")
        return context