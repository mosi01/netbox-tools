"""
service_detail.py
=================

Detail view for a single Service object in the NetBox Tools (nbtools) plugin.

This view uses NetBox's ObjectView so the page renders using the native
NetBox 4.5 object layout:

- Standard object header (title, breadcrumbs, action buttons)
- Native styling
- Works with feature views (changelog, journal, etc.)
- Supports future tab extensions

This file is the direct equivalent of your updated ApplicationDetailView.
"""

import logging
from netbox.views.generic import ObjectView

from ..models import Service

logger = logging.getLogger("nbtools")


class ServiceDetailView(ObjectView):
    """
    Render the detail view for a single Service.

    Template:
        nbtools/services/service_detail.html

    Context provided:
        object            -> The Service instance
        service           -> Same instance for convenience
        applications      -> Related applications (reverse relation)
    """

    # ObjectView requires queryset (not model = ...)
    queryset = Service.objects.all()

    # Using a dedicated, modern NetBox-styled detail template
    template_name = "nbtools/services/service_detail.html"

    def get_extra_context(self, request, instance):
        """
        Add custom context needed by the template.

        `instance` is the Service object being viewed.
        """
        logger.debug("Rendering detail view for Service id=%s", instance.pk)

        return {
            "object": instance,
            "service": instance,
            "applications": instance.applications.all(),
        }