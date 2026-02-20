"""
change_log_views.py
===================

Change log views for the NetBox Tools (nbtools) plugin.

These views use NetBox's built-in ObjectChangeLogView to display the
change history for Service and Application plugin models.

Relevant URL names (defined in urls.py):

- plugins:nbtools:application_changelog
- plugins:nbtools:service_changelog
"""

import logging

from netbox.views.generic import ObjectChangeLogView

from ..models import Application, Service

# Module-level logger (optional, useful for debugging)
logger = logging.getLogger("nbtools")


class ApplicationChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Application.

    This view is used when reversing the URL name 'application_changelog'
    for the Application model, for example:

        {% url 'plugins:nbtools:application_changelog' pk=object.pk %}
    """

    # ObjectChangeLogView will infer the model from this queryset
    queryset = Application.objects.all()


class ServiceChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Service.

    This view is used when reversing the URL name 'service_changelog'
    for the Service model, for example:

        {% url 'plugins:nbtools:service_changelog' pk=object.pk %}
    """

    queryset = Service.objects.all()