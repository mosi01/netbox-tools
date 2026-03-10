"""
application_detail.py
=====================

Detail view for a single Application object in the NetBox Tools (nbtools) plugin.

This view uses NetBox's generic ObjectView together with the
generic/object.html template, so you get:

- Standard object header (title, breadcrumbs)
- Standard action buttons (Edit / Delete / Changelog), where defined
- Consistent layout with the rest of NetBox 4.5
"""

import logging

from netbox.views.generic import ObjectView

from ..models import Application

# Optional logger for debugging
logger = logging.getLogger("nbtools")


class ApplicationDetailView(ObjectView):
    queryset = Application.objects.all()
    template_name = "nbtools/applications/application_detail.html"

    def get_extra_context(self, request, instance):
        return {
            "object": instance,
            "devices": instance.devices.all(),
            "virtual_machines": instance.virtual_machines.all(),
        }