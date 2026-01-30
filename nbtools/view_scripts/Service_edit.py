"""
Service_edit.py

Object edit view for Service objects in the NetBox Tools plugin.
Handles both creation and editing of Service instances.
"""

import logging

from netbox.views.generic import ObjectEditView

from ..models import Service
from ..forms import ServiceForm

logger = logging.getLogger("nbtools")


class ServiceEditView(ObjectEditView):
    """
    Create/edit view for Services.

    URL patterns (in urls.py) should wire:

      * /plugins/nbtools/services/add/       -> ServiceEditView
      * /plugins/nbtools/services/<pk>/edit -> ServiceEditView
    """

    queryset = Service.objects.all()
    form = ServiceForm