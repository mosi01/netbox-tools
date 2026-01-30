"""
Service_list.py

NetBox Tools plugin - list view for Service objects.

This view uses NetBox's ObjectListView together with the ServiceTable
and ServiceFilterSet to render a Device-like list.
"""

import logging

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
    standard UI look & feel.
    """

    queryset = Service.objects.all().prefetch_related("service_owner")
    table = ServiceTable
    filterset = ServiceFilterSet
    template_name = "generic/object_list.html"