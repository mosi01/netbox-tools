"""
application_edit.py
====================

Form-based create/edit view for Application objects in the NetBox Tools
(nbtools) plugin.

Key points for NetBox 4.5 compatibility:

- Uses generic/object_edit.html, which requires:
    * context["object"]      -> model instance (NEVER None)
    * context["object_type"] -> model class (Application)

- When adding a new Application, we construct an unsaved instance:
    object = Application()
  so that object._meta is available in the template.

- Redirects after save to the detail URL named "application"
  (not "application_detail"), because urls.py uses:

    path("applications/<int:pk>/", ..., name="application")
"""

import logging

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from ..models import Application
from ..forms import ApplicationForm

logger = logging.getLogger("nbtools")


class ApplicationEditView(View):
    """Create/edit Application objects using generic/object_edit.html."""

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """
        Return an Application instance.

        - If pk is None, return a NEW unsaved instance (for "add" view).
        - If pk is provided, fetch the existing object or 404.
        """
        if pk is None:
            return Application()
        return get_object_or_404(Application, pk=pk)

    def get(self, request, pk=None):
        """Render the blank or pre-filled form."""
        object = self.get_object(pk)
        form = ApplicationForm(instance=object)

        # Determine where to go after a successful save
        if object.pk:
            return_url = reverse("plugins:nbtools:application", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # NetBox generic/object_edit.html expects "object" and "object_type"
        context = {
            "form": form,
            "object": object,
            "object_type": Application,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        """Handle form submission (create or update)."""
        object = self.get_object(pk)
        form = ApplicationForm(request.POST, instance=object)

        if form.is_valid():
            object = form.save()
            # Redirect to the DETAIL view named "application"
            return redirect(
                reverse("plugins:nbtools:application", args=[object.pk])
            )

        # Form invalid: re-render with errors
        if object.pk:
            return_url = reverse("plugins:nbtools:application", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        context = {
            "form": form,
            "object": object,
            "object_type": Application,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)