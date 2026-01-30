"""
application_edit.py
Form-based create/edit view for Application objects in the NetBox Tools plugin.

IMPORTANT:
NetBox's generic/object_edit.html template requires TWO context variables:
  - `object`: the actual instance (or None when adding)
  - `object_type`: the model class (Application)

If object_type is not provided, the template will attempt:
    object|meta:"verbose_name"
When object is None, this becomes None._meta and crashes.

This file fixes that by passing both `object` and `object_type`.
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
        """Return Application instance or None when creating."""
        if pk is None:
            return None
        return get_object_or_404(Application, pk=pk)

    def get(self, request, pk=None):
        """Render form for add/edit."""
        object = self.get_object(pk)
        form = ApplicationForm(instance=object)

        # Determine return URL
        if object:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # REQUIRED BY NETBOX GENERIC EDIT TEMPLATE:
        context = {
            "form": form,
            "object": object,
            "object_type": Application,  # <-- FIX
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

        # Determine return URL for failed form
        if object:
            return_url = reverse("plugins:nbtools:application_detail", args=[object.pk])
        else:
            return_url = reverse("plugins:nbtools:application_list")

        # REQUIRED BY NETBOX GENERIC EDIT TEMPLATE:
        context = {
            "form": form,
            "object": object,
            "object_type": Application,  # <-- FIX
            "return_url": return_url,
        }

        return render(request, self.template_name, context)