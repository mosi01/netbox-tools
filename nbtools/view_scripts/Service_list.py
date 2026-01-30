from django.views.generic import ListView
from django.db.models import Q

from .models import Service

class ServiceListView(ListView):
    """
    List view for Services.

    Similar to ApplicationListView, with quick search and pagination.
    """
    model = Service
    template_name = "nbtools/applications/service_list.html"
    context_object_name = "services"
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(display_name__icontains=q)
                | Q(description__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        return context
