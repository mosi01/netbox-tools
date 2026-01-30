"""
views.py

Main view entrypoints for the NetBox Tools plugin.
"""

# Import view_scripts
from .view_scripts.Documentation_binding import DocumentationBindingView
from .view_scripts.IP_prefix_checker import IPPrefixCheckerView
from .view_scripts.Prefix_validator import PrefixValidatorView
from .view_scripts.Documentation_reviewer import DocumentationReviewerView
from .view_scripts.Serial_checker import SerialChecker
from .view_scripts.VM_tool import VMToolView

from .view_scripts.Application_detail import ApplicationDetailView
from .view_scripts.Application_list import ApplicationListView
from .view_scripts.Application_edit import ApplicationEditView

from .view_scripts.Service_detail import ServiceDetailView
from .view_scripts.Service_list import ServiceListView
from .view_scripts.Service_edit import ServiceEditView
from .view_scripts.delete_views import ApplicationDeleteView, ServiceDeleteView

from django.shortcuts import render

from dcim.models import Device
from virtualization.models import VirtualMachine

import logging

logger = logging.getLogger("nbtools")


def dashboard(request):
    """
    Simple plugin dashboard showing some high-level statistics.
    """
    context = {
        "device_count": Device.objects.count(),
        "vm_count": VirtualMachine.objects.count(),
    }

    return render(request, "nbtools/dashboard.html", context)