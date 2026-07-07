from netbox.views import generic
from django.urls import reverse

from nbtools.models import FortiSwitchPortConfiguration
from nbtools.forms import FortiSwitchPortConfigurationForm


class FortiSwitchPortConfigurationListView(generic.ObjectListView):
    queryset = FortiSwitchPortConfiguration.objects.select_related("site")
    table = None  # optional if using table class later


class FortiSwitchPortConfigurationEditView(generic.ObjectEditView):
    queryset = FortiSwitchPortConfiguration.objects.all()
    form = FortiSwitchPortConfigurationForm


class FortiSwitchPortConfigurationDeleteView(generic.ObjectDeleteView):
    queryset = FortiSwitchPortConfiguration.objects.all()
