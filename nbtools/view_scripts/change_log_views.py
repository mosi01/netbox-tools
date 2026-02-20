"""
change_log_views.py
===================

Correct changelog views for the NetBox Tools (nbtools) plugin.

IMPORTANT for NetBox 4.5:
-------------------------
ObjectChangeLogView *requires* the model to be passed into .as_view()
via the URL route, not only defined as a class attribute.

Therefore the view classes MUST NOT override .get(), .dispatch(), etc.
"""

from netbox.views.generic import ObjectChangeLogView

from ..models import Application, Service


class ApplicationChangeLogView(ObjectChangeLogView):
    """Changelog view for the Application model."""
    queryset = Application.objects.all()


class ServiceChangeLogView(ObjectChangeLogView):
    """Changelog view for the Service model."""
    queryset = Service.objects.all()
