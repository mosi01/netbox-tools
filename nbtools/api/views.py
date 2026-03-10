"""
views.py
========

REST API viewsets for the NetBox Tools (nbtools) plugin.

These viewsets expose the Service and Application models over the
NetBox plugin API. They are also required by NetBox's event system,
which uses the API serializers & viewsets to serialize objects for
webhooks and other event consumers.

API base path (after configuration in the plugin's config class):

    /api/plugins/nbtools/services/
    /api/plugins/nbtools/applications/
"""

from netbox.api.viewsets import NetBoxModelViewSet

from ..models import Service, Application
from .serializers import ServiceSerializer, ApplicationSerializer


class ServiceViewSet(NetBoxModelViewSet):
    """
    API endpoint for viewing and editing Service objects.
    """

    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class ApplicationViewSet(NetBoxModelViewSet):
    """
    API endpoint for viewing and editing Application objects.
    """

    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer