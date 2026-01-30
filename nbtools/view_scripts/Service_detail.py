from django.views.generic import DetailView
from .models import Service



class ServiceDetailView(DetailView):
    """
    Detail view for a single Service.

    Shows the basic info and its related Applications.
    """
    model = Service
    template_name = "nbtools/applications/service_detail.html"
    context_object_name = "service"
