"""
change_log_views.py
===================

Change log views for the NetBox Tools (nbtools) plugin.

These views use NetBox's built-in ObjectChangeLogView to display the
change history for Service and Application plugin models.

NetBox expects the following route names for change logs of plugin
NetBoxModel subclasses:

  - plugins:nbtools:application_changelog
  - plugins:nbtools:service_changelog

These are wired up in urls.py.
"""

import logging

from netbox.views.generic import ObjectChangeLogView

from ..models import Application, Service

# Set up a module-level logger (optional but useful for debugging)
logger = logging.getLogger("nbtools")


class ApplicationChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Application.

    This view is used when reversing the URL name 'application_changelog'
    for the Application model, e.g.:

        plugins:nbtools:application_changelog
    """

    queryset = Application.objects.all()


class ServiceChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Service.

    This view is used when reversing the URL name 'service_changelog'
    for the Service model, e.g.:

        plugins:nbtools:service_changelog
    """

    queryset = Service.objects.all()