"""
serializers.py
==============

REST API serializers for the NetBox Tools (nbtools) plugin models.

These serializers are required by NetBox's events system, which calls
get_serializer_for_model() to serialize NetBoxModel instances when
emitting events (webhooks, etc.).

For a plugin model `Application` in app `nbtools`, NetBox expects to
find:

    nbtools.api.serializers.ApplicationSerializer

Similarly for `Service`:

    nbtools.api.serializers.ServiceSerializer

Reference: NetBox 4.5 plugin REST API docs.
"""

from netbox.api.serializers import NetBoxModelSerializer
from ..models import Service, Application


class ServiceSerializer(NetBoxModelSerializer):
    """
    Serializer for the nbtools.Service model.

    This exposes all model fields for use via the REST API and for
    internal event serialization.
    """

    class Meta:
        model = Service
        fields = "__all__"


class ApplicationSerializer(NetBoxModelSerializer):
    """
    Serializer for the nbtools.Application model.

    This exposes all model fields for use via the REST API and for
    internal event serialization.
    """

    class Meta:
        model = Application
        fields = "__all__"