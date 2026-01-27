#Import view_scripts
from .view_scripts.Documentation_binding import DocumentationBindingView
from .view_scripts.IP_prefix_checker import IPPrefixCheckerView
from .view_scripts.Prefix_validator import PrefixValidatorView
from .view_scripts.Documentation_reviewer import DocumentationReviewerView

from django.shortcuts import render

from dcim.models import Device
from virtualization.models import VirtualMachine

import logging


logger = logging.getLogger("nbtools")



def dashboard(request):

	context = {
		"device_count": Device.objects.count(),
		"vm_count": VirtualMachine.objects.count(),
	}

	return render(request, "nbtools/dashboard.html", context)
