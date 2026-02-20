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
    """
    Render the detail view for a single Application instance.

    Template:
        nbtools/applications/application_detail.html

    Context:
        object            -> Application instance (provided by ObjectView)
        application       -> Same Application instance (for convenience)
        devices           -> Related Device queryset
        virtual_machines  -> Related VirtualMachine queryset
    """

    # ObjectView expects a queryset to resolve the object from the URL pk
    queryset = Application.objects.all()

    # Use our plugin template, which extends generic/object.html
    template_name = "nbtools/applications/application_detail.html"

    def get_extra_context(self, request, instance):
        """
        Add extra context for the template.

        `instance` is the Application object being viewed.
        """
        logger.debug("Rendering detail view for Application id=%s", instance.pk)

        return {
            "application": instance,
            "devices": instance.devices.all(),
            "virtual_machines": instance.virtual_machines.all(),
        }