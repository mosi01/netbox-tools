"""
service_edit.py
================

Form-based create/edit view for Service objects in the NetBox Tools
(nbtools) plugin.

Key points for NetBox 4.5 compatibility:

- Uses generic/object_edit.html, which requires:
    * context["object"]      -> model instance (NEVER None)
    * context["object_type"] -> model class (Service)

- When adding a new Service, we construct an unsaved instance:
    object = Service()
  so that object._meta is available in the template.

- Redirects after save to the detail URL named "service"
  (not "service_detail"), because urls.py uses:

    path("services/<int:pk>/", ..., name="service")
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

      * /plugins/nbtools/services/add/         -> create new
      * /plugins/nbtools/services/<pk>/edit/  -> edit existing

    Template:

      * generic/object_edit.html

    Context:

      * form        - the bound/unbound ServiceForm
      * object      - the Service instance (unsaved on add)
      * object_type - the Service class
      * return_url  - redirect target after save
    """

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """
        Fetch a Service instance or return a NEW unsaved one if pk is None.
        """
        if pk is None:
            return Service()
        return get_object_or_404(Service, pk=pk)

    def get(self, request, pk=None):
        """Handle GET: render form for add or edit."""
        object = self.get_object(pk)
        form = ServiceForm(instance=object)

        if object.pk:
            return_url = reverse("plugins:nbtools:service", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:service_list")

        context = {
            "form": form,
            "object": object,
            "object_type": Service,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        """Handle POST: validate, save, and redirect."""
        object = self.get_object(pk)
        form = ServiceForm(request.POST, instance=object)

        if form.is_valid():
            object = form.save()
            return redirect(
                reverse("plugins:nbtools:service", args=[object.pk])
            )

        if object.pk:
            return_url = reverse("plugins:nbtools:service", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:service_list")

        context = {
            "form": form,
            "object": object,
            "object_type": Service,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)