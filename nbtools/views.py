"""
views.py

Main view entrypoints for the NetBox Tools plugin.

This file acts as a thin import/dispatcher layer so that urls.py can
reference views via `from . import views`.

Compatible with NetBox 4.5.x / 4.6.x plugin structure.
"""

from django.shortcuts import render

from dcim.models import Device
from virtualization.models import VirtualMachine

import logging

# ----------------------------------------------------------------------
# Existing modular view scripts
# ----------------------------------------------------------------------
from .view_scripts.Documentation_binding import DocumentationBindingView
from .view_scripts.IP_prefix_checker import IPPrefixCheckerView
from .view_scripts.Prefix_validator import PrefixValidatorView
from .view_scripts.Documentation_reviewer import DocumentationReviewerView
from .view_scripts.Serial_checker import SerialChecker
from .view_scripts.VM_tool import VMToolView

# Existing FortiGate / FortiSwitch tools
from .view_scripts.Fortigate_policy_toolset import FortigatePolicyToolsetView
from .view_scripts.fortiswitch_port_tool import FortiSwitchPortToolView

# FortiSiteBinding CRUD + changelog views
from .view_scripts.forti_site_binding_views import (
    FortiSiteBindingListView,
    FortiSiteBindingView,
    FortiSiteBindingEditView,
    FortiSiteBindingDeleteView,
    FortiSiteBindingChangeLogView,   # <-- CRITICAL FIX
)

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
