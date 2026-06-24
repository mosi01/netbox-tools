"""
CRUD views for FortiSiteBinding.
"""

from netbox.views import generic

from ..models import FortiSiteBinding
from ..tables import FortiSiteBindingTable
from ..forms import FortiSiteBindingForm


class FortiSiteBindingListView(generic.ObjectListView):
    queryset = FortiSiteBinding.objects.all()
    table = FortiSiteBindingTable


class FortiSiteBindingView(generic.ObjectView):
    queryset = FortiSiteBinding.objects.all()


class FortiSiteBindingEditView(generic.ObjectEditView):
    queryset = FortiSiteBinding.objects.all()
    form = FortiSiteBindingForm


class FortiSiteBindingDeleteView(generic.ObjectDeleteView):
    queryset = FortiSiteBinding.objects.all()
