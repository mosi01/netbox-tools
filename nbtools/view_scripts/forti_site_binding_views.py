"""
forti_site_binding_views.py

CRUD views for FortiSiteBinding.

✅ FIXES:
- Proper handling of ADD vs EDIT
- Prevents /None redirect issue
"""

from netbox.views import generic

from ..models import FortiSiteBinding
from ..tables import FortiSiteBindingTable
from ..forms import FortiSiteBindingForm


# ================================================================
# LIST VIEW
# ================================================================
class FortiSiteBindingListView(generic.ObjectListView):
    queryset = FortiSiteBinding.objects.all()
    table = FortiSiteBindingTable


# ================================================================
# DETAIL VIEW
# ================================================================
class FortiSiteBindingView(generic.ObjectView):
    queryset = FortiSiteBinding.objects.all()


# ================================================================
# ADD / EDIT VIEW (✅ FIXED)
# ================================================================
class FortiSiteBindingEditView(generic.ObjectEditView):
    queryset = FortiSiteBinding.objects.all()
    form = FortiSiteBindingForm

    def get_object(self, *args, **kwargs):
        """
        ✅ CRITICAL FIX

        Ensures:
        - ADD → returns None (new object)
        - EDIT → returns existing object
        """

        if "pk" in kwargs:
            return super().get_object(*args, **kwargs)

        # This makes "add" work correctly
        return None


# ================================================================
# DELETE VIEW
# ================================================================
class FortiSiteBindingDeleteView(generic.ObjectDeleteView):
    queryset = FortiSiteBinding.objects.all()
