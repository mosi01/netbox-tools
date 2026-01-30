
from django.views.generic import ListView
from django.db.models import Q

from .models import Application

class ApplicationListView(ListView):
    """
    List view for Applications.

    This will later be wired to a template that looks similar to the
    built-in Device list (with filters, search, add/import/export etc.).
    For now it provides:
      * Pagination
      * Simple quick search on name/display_name/description
    """
    model = Application
    template_name = "nbtools/applications/application_list.html"
    context_object_name = "applications"
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
        # Preserve search query in the context
        context["search_query"] = self.request.GET.get("q", "")
        return context
