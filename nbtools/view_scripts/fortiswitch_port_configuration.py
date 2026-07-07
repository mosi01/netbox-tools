from netbox.views import generic
from django.urls import reverse

from nbtools.models import FortiSwitchPortConfiguration
from nbtools.forms import FortiSwitchPortConfigurationForm
from nbtools.tables import FortiSwitchPortConfigurationTable
from nbtools.filtersets import FortiSwitchPortConfigurationFilterSet


class FortiSwitchPortConfigurationView(generic.ObjectView):
    queryset = FortiSwitchPortConfiguration.objects.select_related("site")

class FortiSwitchPortConfigurationListView(generic.ObjectListView):
    queryset = FortiSwitchPortConfiguration.objects.select_related("site")
    table = FortiSwitchPortConfigurationTable
    filterset = FortiSwitchPortConfigurationFilterSet


class FortiSwitchPortConfigurationEditView(generic.ObjectEditView):
    queryset = FortiSwitchPortConfiguration.objects.all()
    form = FortiSwitchPortConfigurationForm


class FortiSwitchPortConfigurationDeleteView(generic.ObjectDeleteView):
    queryset = FortiSwitchPortConfiguration.objects.all()


class FortiSwitchPortConfigurationChangeLogView(generic.ObjectChangeLogView):
    queryset = FortiSwitchPortConfiguration.objects.all()
