"""
Application_edit.py

Object edit view for Application objects in the NetBox Tools plugin.
Handles both creation and editing of Application instances.
"""

import logging

from netbox.views.generic import ObjectEditView

from ..models import Application
from ..forms import ApplicationForm

logger = logging.getLogger("nbtools")


class ApplicationEditView(ObjectEditView):
    """
    Create/edit view for Applications.

    URL patterns (in urls.py) should wire:

      * /plugins/nbtools/applications/add/       -> ApplicationEditView
      * /plugins/nbtools/applications/<pk>/edit -> ApplicationEditView
    """

    queryset = Application.objects.all()
    form = ApplicationForm