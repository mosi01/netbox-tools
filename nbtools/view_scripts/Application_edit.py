"""
application_edit.py

Form-based create/edit view for Application objects in the NetBox Tools
plugin.

Important:
This view intentionally does NOT use NetBox's ObjectEditView or the REST
API serializers. Instead, it uses a standard Django GET/POST pattern with
NetBoxModelForm, rendering the generic/object_edit.html template. This
avoids the SerializerNotFound error when a DRF serializer is not defined
for nbtools.Application.
"""

import logging

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from ..models import Application
from ..forms import ApplicationForm

logger = logging.getLogger("nbtools")


class ApplicationEditView(View):
    """
    Create/edit view for Applications.

    URL patterns (in urls.py):

      * /plugins/nbtools/applications/add/        -> create new
      * /plugins/nbtools/applications/<pk>/edit/ -> edit existing

    Template:
      * generic/object_edit.html

    Context:
      * form       - the bound/unbound ApplicationForm
      * obj        - the Application instance, or None when adding
      * return_url - URL to redirect to on successful save
    """

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """
        Helper to fetch an Application instance or return None if pk is
        not provided (i.e. creating a new object).
        """
        if pk is None:
            return None
        return get_object_or_404(Application, pk=pk)

    def get(self, request, pk=None):
        """
        Handle GET requests:

          * If pk is provided, load existing object and populate form.
          * If no pk, create a blank form for a new Application.
        """
        obj = self.get_object(pk)
        form = ApplicationForm(instance=obj)

        # Where to go after a successful save
        if obj:
            return_url = reverse("plugins:nbtools:application_detail", args=[obj.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

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
        form = ApplicationForm(request.POST, instance=obj)

        if form.is_valid():
            obj = form.save()

            # Redirect to the detail view of the saved object
            return redirect(
                reverse("plugins:nbtools:application_detail", args=[obj.pk])
            )

        # If the form is invalid, render the template with errors
        if obj:
            return_url = reverse("plugins:nbtools:application_detail", args=[obj.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        context = {
            "form": form,
            "obj": obj,
            "return_url": return_url,
        }
        return render(request, self.template_name, context)