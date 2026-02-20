from netbox.views.generic import ObjectView
from ..models import Application


class ApplicationDetailView(ObjectView):
    """
    NetBox Tools plugin
    ===================

    Detail view for a single Application object.

    This uses NetBox's generic ObjectView + generic/object.html template,
    so the page gets:
      - Standard object header (breadcrumb, name, status)
      - Standard action buttons (Edit / Delete / Changelog / etc.)
      - Standard layout with left/right content columns
      - Compatibility with tabs if you later add more model views
    """

    # ObjectView uses queryset, not model, to retrieve the instance
    queryset = Application.objects.all()

    # We still point to a plugin-specific template, but that template
    # will now EXTEND generic/object.html instead of base/layout.html.
    template_name = "nbtools/applications/application_detail.html"

    def get_extra_context(self, request, instance):
        """
        Provide extra context for the template.

        `instance` is the Application object being viewed.
        We expose related Devices and Virtual Machines separately for
        convenience, although you can still access `instance.devices.all`
        and `instance.virtual_machines.all` directly in the template.
        """
        return {
            "application": instance,
            "devices": instance.devices.all(),
            "virtual_machines": instance.virtual_machines.all(),
        }