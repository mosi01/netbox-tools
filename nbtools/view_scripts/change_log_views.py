
"""
change_log_views.py
===================

Change log views for the NetBox Tools (nbtools) plugin.

These views use NetBox's built-in ObjectChangeLogView to display
the change history for Service and Application plugin models.

NetBox 4.5 requires that plugin changelog views define BOTH:
  - model
  - queryset
"""

import logging

from netbox.views.generic import ObjectChangeLogView

from ..models import Application, Service


logger = logging.getLogger("nbtools")


class ApplicationChangeLogView(ObjectChangeLogView):
    """
    Changelog view for the Application model.
    """
    model = Application                                 # REQUIRED
    queryset = Application.objects.all()                # REQUIRED


class ServiceChangeLogView(ObjectChangeLogView):
    """
    Changelog view for the Service model.
    """
    model = Service                                     # REQUIRED
    queryset = Service.objects.all()                    # FIXED: removed trailing comma
