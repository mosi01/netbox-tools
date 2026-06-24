"""
forti_site_binding_views.pySiteBinding model.forti_site_binding_views.py

This file contains:
- List view
- Detail view
- Create/Edit view
- Delete view
- Changelog view

Compatible with NetBox 4.5.x / 4.6.x style generic views.
"""

from netbox.views import generic

from ..models import FortiSiteBinding
from ..forms import FortiSiteBindingForm
from ..tables import FortiSiteBindingTable


class FortiSiteBindingListView(generic.ObjectListView):
    """
    List all FortiSiteBinding objects.
    """
    queryset = FortiSiteBinding.objects.all()
    table = FortiSiteBindingTable


class FortiSiteBindingView(generic.ObjectView):
    """
    Display one FortiSiteBinding object.
    """
    queryset = FortiSiteBinding.objects.all()


class FortiSiteBindingEditView(generic.ObjectEditView):
    """
    Create or edit a FortiSiteBinding object.
    """
    queryset = FortiSiteBinding.objects.all()
    form = FortiSiteBindingForm


class FortiSiteBindingDeleteView(generic.ObjectDeleteView):
    """
    Delete a FortiSiteBinding object.
    """
    queryset = FortiSiteBinding.objects.all()


class FortiSiteBindingChangeLogView(generic.ObjectChangeLogView):
    """
    Display the change history for a FortiSiteBinding object.
    """
    queryset = FortiSiteBinding.objects.all()


