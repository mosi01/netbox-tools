from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from nbtools.forms import FortiSwitchPortConfigurationForm
from nbtools.models import FortiSwitchPortConfiguration


class FortiSwitchPortConfigurationListView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    """
    List predefined FortiSwitch port configurations.
    """

    permission_required = "nbtools.view_fortiswitchportconfiguration"
    template_name = "nbtools/fortiswitch_port_configuration_list.html"

    def get(self, request):
        configurations = (
            FortiSwitchPortConfiguration.objects
            .select_related("site")
            .order_by("site__name", "name")
        )

        return render(
            request,
            self.template_name,
            {
                "configurations": configurations,
                "can_add": request.user.has_perm(
                    "nbtools.configure_fortiswitchportconfiguration"
                ),
            },
        )


class FortiSwitchPortConfigurationEditView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    """
    Create or edit a predefined FortiSwitch port configuration.
    """

    permission_required = "nbtools.configure_fortiswitchportconfiguration"
    template_name = "nbtools/fortiswitch_port_configuration_edit.html"

    def get_object(self, pk):
        if pk:
            return get_object_or_404(FortiSwitchPortConfiguration, pk=pk)
        return FortiSwitchPortConfiguration()

    def get(self, request, pk=None):
        obj = self.get_object(pk)
        form = FortiSwitchPortConfigurationForm(instance=obj)

        return render(
            request,
            self.template_name,
            {
                "object": obj,
                "form": form,
            },
        )

    def post(self, request, pk=None):
        obj = self.get_object(pk)
        form = FortiSwitchPortConfigurationForm(request.POST, instance=obj)

        if form.is_valid():
            form.save()
            messages.success(request, "FortiSwitch port configuration saved.")
            return redirect("plugins:nbtools:fortiswitch_port_configuration_list")

        return render(
            request,
            self.template_name,
            {
                "object": obj,
                "form": form,
            },
        )


class FortiSwitchPortConfigurationDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    """
    Delete a predefined FortiSwitch port configuration.
    """

    permission_required = "nbtools.configure_fortiswitchportconfiguration"
    template_name = "nbtools/fortiswitch_port_configuration_delete.html"

    def get(self, request, pk):
        obj = get_object_or_404(FortiSwitchPortConfiguration, pk=pk)

        return render(
            request,
            self.template_name,
            {
                "object": obj,
            },
        )

    def post(self, request, pk):
        obj = get_object_or_404(FortiSwitchPortConfiguration, pk=pk)
        obj.delete()

        messages.success(request, "FortiSwitch port configuration deleted.")
        return redirect("plugins:nbtools:fortiswitch_port_configuration_list")
