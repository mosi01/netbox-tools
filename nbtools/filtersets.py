"""
filtersets.py

NetBox Tools plugin - filtersets for Application and Service models.

These filter sets drive both the UI filters (right-hand filter form)
and REST API filtering for these models.
"""

from netbox.filtersets import NetBoxModelFilterSet, register_filterset
from django_filters import CharFilter, ModelMultipleChoiceFilter
from django.db import models

from tenancy.models import Contact
from dcim.models import Device
from virtualization.models import VirtualMachine

from .models import Application, Service


@register_filterset
class ServiceFilterSet(NetBoxModelFilterSet):
    """
    FilterSet for the Service model.

    Supports filtering by:
      - name
      - display_name
      - description (search via q)
      - service_owner
    """

    q = CharFilter(
        method="search",
        label="Search",
    )

    class Meta:
        model = Service
        fields = (
            "name",
            "display_name",
            "service_owner",
        )

    def search(self, queryset, name, value):
        """
        Basic search method for 'q' parameter.
        """
        if not value.strip():
            return queryset
        value = value.strip()
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(display_name__icontains=value)
            | models.Q(description__icontains=value)
        )


@register_filterset
class ApplicationFilterSet(NetBoxModelFilterSet):
    """
    FilterSet for the Application model.

    Supports filtering by:
      - name
      - display_name
      - status
      - service
      - application_owner
      - technical_contact
      - related devices
      - related virtual machines
      - generic 'q' search
    """

    q = CharFilter(
        method="search",
        label="Search",
    )

    devices = ModelMultipleChoiceFilter(
        field_name="devices",
        queryset=Device.objects.all(),
        label="Devices",
    )

    virtual_machines = ModelMultipleChoiceFilter(
        field_name="virtual_machines",
        queryset=VirtualMachine.objects.all(),
        label="Virtual Machines",
    )

    application_owner = ModelMultipleChoiceFilter(
        field_name="application_owner",
        queryset=Contact.objects.all(),
        label="Application Owner",
    )

    technical_contact = ModelMultipleChoiceFilter(
        field_name="technical_contact",
        queryset=Contact.objects.all(),
        label="Technical Contact",
    )

    class Meta:
        model = Application
        fields = (
            "name",
            "display_name",
            "status",
            "service",
            "application_owner",
            "technical_contact",
            "devices",
            "virtual_machines",
        )

    def search(self, queryset, name, value):
        """
        Basic search method for 'q' parameter.
        """
        if not value.strip():
            return queryset
        value = value.strip()
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(display_name__icontains=value)
            | models.Q(description__icontains=value)
        )