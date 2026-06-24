"""
forti_site_binding for FortiSiteBinding.forti_site_binding_views.py

Implements full CRUD + changelog support in NetBox 4.5 style.
"""

from netbox.views import generic

from ..models import FortiSiteBinding
from ..forms import FortiSiteBindingForm
from ..tables import FortiSiteBindingTable


# ---------------------------------------------------------------------------
# LIST VIEW
# ---------------------------------------------------------------------------
class FortiSiteBindingListView(generic.ObjectListView):
    """
    List all FortiSiteBinding objects.
    """
    queryset = FortiSiteBinding.objects.all()
    table = FortiSiteBindingTable


# ---------------------------------------------------------------------------
# DETAIL VIEW
# ---------------------------------------------------------------------------
class FortiSiteBindingView(generic.ObjectView):
    """
    Display a single FortiSiteBinding.
    """
    queryset = FortiSiteBinding.objects.all()


# ---------------------------------------------------------------------------
# CREATE / EDIT VIEW
# ---------------------------------------------------------------------------
class FortiSiteBindingEditView(generic.ObjectEditView):
    """
    Create or edit FortiSiteBinding.
    """
    queryset = FortiSiteBinding.objects.all()
    form = FortiSiteBindingForm


# ---------------------------------------------------------------------------
# DELETE VIEW
# ---------------------------------------------------------------------------
class FortiSiteBindingDeleteView(generic.ObjectDeleteView):
    """
    Delete FortiSiteBinding.
    """
    queryset = FortiSiteBinding.objects.all()


# ---------------------------------------------------------------------------
# CHANGELOG VIEW 
# ---------------------------------------------------------------------------
class FortiSiteBindingChangeLogView(generic.ObjectChangeLogView):
    """
    View change history for FortiSiteBinding.

    This enables:
    - Changelog button
    - Audit history
    - Prevents NoReverseMatch errors
    """
    queryset = FortiSiteBinding.objects.all()
