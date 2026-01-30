"""
service_edit.py

Form-based create/edit view for Service objects in the NetBox Tools
plugin.

Like ApplicationEditView, this avoids ObjectEditView and API serializers
to prevent SerializerNotFound and instead uses a standard Django form
handling pattern.
"""

import logging

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from ..models import Service
from ..forms import ServiceForm

logger = logging.getLogger("nbtools")


class ServiceEditView(View):
    """
    Create/edit view for Services.

    URL patterns (in urls.py):

      * /plugins/nbtools/services/add/        -> create new
      * /plugins/nbtools/services/<pk>/edit/ -> edit existing

    Template:
      * generic/object_edit.html

    Context:
      * form       - the bound/unbound ServiceForm
      * obj        - the Service instance, or None when adding
      * return_url - URL to redirect to on successful save
    """

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """
        Helper to fetch a Service instance or return None if pk is
        not provided (i.e. creating a new object).
        """
        if pk is None:
            return None
        return get_object_or_404(Service, pk=pk)

    def get(self, request, pk=None):
        """
        Handle GET requests:

          * If pk is provided, load existing object and populate form.
          * If no pk, create a blank form for a new Service.
        """
        obj = self.get_object(pk)
        form = ServiceForm(instance=obj)

        if obj:
            return_url = reverse("plugins:nbtools:service_detail", args=[obj.pk])
        else:
            return_url = reverse("plugins:nbtools:service_list")

        context = {
            "form": form,
            "obj": obj,
            "return_url": return_url,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        """
        Handle POST requests:

          * Validate and save form
          * Redirect to detail view for the created/edited object
          * Redisplay form with errors if invalid
        """
        obj = self.get_object(pk)
        form = ServiceForm(request.POST, instance=obj)

        if form.is_valid():
            obj = form.save()
            return redirect(
                reverse("plugins:nbtools:service_detail", args=[obj.pk])
            )

        if obj:
            return_url = reverse("plugins:nbtools:service_detail", args=[obj.pk])
        else:
            return_url = reverse("plugins:nbtools:service_list")

        context = {
            "form": form,
            "obj": obj,
            "return_url": return_url,
        }
        return render(request, self.template_name, context)