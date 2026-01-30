
from django.views.generic import DetailView
from django.db.models import Q


from ..models import Application


class ApplicationDetailView(DetailView):
    """
    Detail view for a single Application.

    From here you will later see:
      * Basic attributes (status, description, owners)
      * Linked Devices and Virtual Machines
      * Possibly related documentation from SharePoint
    """
    model = Application
    template_name = "nbtools/applications/application_detail.html"
    context_object_name = "application"
