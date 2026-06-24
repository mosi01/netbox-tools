"""
forti_site_binding_views.py

CRUD views for FortiSiteBinding.
"""

from netbox.views import generic

from ..models import FortiSiteBinding
from ..tables import FortiSiteBindingTable
from ..forms import FortiSiteBindingForm


class FortiSiteBindingListView(generic.ObjectListView):
    """
    List view for FortiSiteBinding objects.
    """
    queryset = FortiSiteBinding.objects.all()
    table = FortiSiteBindingTable


class FortiSiteBindingView(generic.ObjectView):
    """
    Detail view for a single FortiSiteBinding object.
    """
    queryset = FortiSiteBinding.objects.all()


class FortiSiteBindingEditView(generic.ObjectEditView):
    """
    Add/edit view for FortiSiteBinding.
    """
    queryset = FortiSiteBinding.objects.all()
    form = FortiSiteBindingForm


class FortiSiteBindingDeleteView(generic.ObjectDeleteView):
    """
    Delete view for FortiSiteBinding.
    """
    queryset = FortiSiteBinding.objects.all()
