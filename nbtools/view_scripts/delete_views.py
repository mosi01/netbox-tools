"""
delete_views.py
===============

Delete views for nbtools Service and Application models.

These use NetBox's built-in ObjectDeleteView, which handles:
- Permission checks
- Confirmation screens
- Post-delete redirects
- Event serialization

Required for:
- application_delete
- service_delete
"""

from netbox.views.generic import ObjectDeleteView
from ..models import Application, Service


class ApplicationDeleteView(ObjectDeleteView):
    queryset = Application.objects.all()


class ServiceDeleteView(ObjectDeleteView):
    queryset = Service.objects.all()