"""
application_edit.py
Form-based create/edit view for Application objects in the NetBox Tools
plugin.

IMPORTANT FIX:
NetBox's generic/object_edit.html template expects the context variable
`object` (NOT `obj`). Without it, the template's {{ object|meta }} call
breaks because `object` becomes a string instead of the real instance.

This version fixes that by renaming the context key from `obj` -> `object`.
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
      * /plugins/nbtools/applications/<pk>/edit/  -> edit existing

    Template:
      * generic/object_edit.html

    Context:
      * form        - the bound/unbound ApplicationForm
      * object      - the Application instance, or None when adding  (IMPORTANT)
      * return_url  - URL to redirect to after save
    """

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """Return an Application instance or None (on object creation)."""
        if pk is None:
            return None
        return get_object_or_404(Application, pk=pk)

    def get(self, request, pk=None):
        """Render the blank or pre-filled form."""
        object = self.get_object(pk)
        form = ApplicationForm(instance=object)

        # Determine return URL
        if object:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # IMPORTANT: NetBox requires context key "object"
        context = {
            "form": form,
            "object": object,      # <-- FIXED
            "return_url": return_url,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        """Handle form submission."""
        object = self.get_object(pk)
        form = ApplicationForm(request.POST, instance=object)

        if form.is_valid():
            object = form.save()
            return redirect(
                reverse("plugins:nbtools:application_detail", args=[object.pk])
            )

        if object:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # IMPORTANT: NetBox requires context key "object"
        context = {
            "form": form,
            "object": object,      # <-- FIXED
            "return_url": return_url,
        }

        return render(request, self.template_name, context)