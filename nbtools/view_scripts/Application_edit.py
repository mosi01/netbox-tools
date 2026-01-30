"""
application_edit.py
Corrected version for NetBox 4.5.x

IMPORTANT:
NetBox's generic/object_edit.html template requires:

  object      -> an instance of the model (NEVER None)
  object_type -> the model class

If object is None, the template tries to do:
    object|meta:"verbose_name"
Which becomes None._meta and crashes.

Therefore, when adding a new Application, we MUST pass:
    object = Application()   # unsaved instance

This is exactly how NetBox's built-in ObjectEditView behaves.
"""

import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from ..models import Application
from ..forms import ApplicationForm

logger = logging.getLogger("nbtools")


class ApplicationEditView(View):
    """Create/edit Application objects."""

    template_name = "generic/object_edit.html"

    def get_object(self, pk):
        """Fetch object or return UNSAVED instance for object creation."""
        if pk is None:
            return Application()   # <-- critical fix (never return None)
        return get_object_or_404(Application, pk=pk)

    def get(self, request, pk=None):
        """Render form."""
        object = self.get_object(pk)
        form = ApplicationForm(instance=object)

        # Return URL
        if object.pk:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # REQUIRED context
        context = {
            "form": form,
            "object": object,        # instance, even when new
            "object_type": Application,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        """Process submitted form."""
        object = self.get_object(pk)
        form = ApplicationForm(request.POST, instance=object)

        if form.is_valid():
            object = form.save()
            return redirect(
                reverse("plugins:nbtools:application_detail", args=[object.pk])
            )

        # Return URL for failed form
        if object.pk:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        context = {
            "form": form,
            "object": object,        # instance, not None
            "object_type": Application,
            "return_url": return_url,
        }

        return render(request, self.template_name, context)