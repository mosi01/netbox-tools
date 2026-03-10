"""
change_log_views.py
===================

Change log views for the NetBox Tools (nbtools) plugin.

These views wrap NetBox's ObjectChangeLogView so that we can use nice,
named view classes for Application and Service, while still satisfying
the base view's requirement for a `model` argument in .get().

Tested against NetBox 4.5.0.
"""

import logging

from netbox.views.generic import ObjectChangeLogView

from ..models import Application, Service


# Optional logger for debugging
logger = logging.getLogger("nbtools")


class ApplicationChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Application.

    URL name: plugins:nbtools:application_changelog
    Route:    /plugins/nbtools/applications/<pk>/changelog/
    """

    # A normal queryset is still good practice
    queryset = Application.objects.all()

    def get(self, request, pk, *args, **kwargs):
        """
        Override get() so we can inject the required `model` argument
        for the base ObjectChangeLogView.

        The parent implementation expects something like:
            get(self, request, model, pk, ...)

        Here we pass model=Application explicitly.
        """
        logger.debug("Rendering changelog for Application id=%s", pk)
        return super().get(request, model=Application, pk=pk, *args, **kwargs)


class ServiceChangeLogView(ObjectChangeLogView):
    """
    Change log view for nbtools.Service.

    URL name: plugins:nbtools:service_changelog
    Route:    /plugins/nbtools/services/<pk>/changelog/
    """

    queryset = Service.objects.all()

    def get(self, request, pk, *args, **kwargs):
        """
        Same pattern as ApplicationChangeLogView, but for Service.
        """
        logger.debug("Rendering changelog for Service id=%s", pk)
        return super().get(request, model=Service, pk=pk, *args, **kwargs)