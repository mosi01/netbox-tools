from django.urls import path
from . import views

app_name = "nbtools"

urlpatterns = [
	path("", views.dashboard, name="dashboard"),
	path("documentation-reviewer/", views.DocumentationReviewerView.as_view(), name="documentation_reviewer"),
	path("serial-checker/", views.SerialChecker.as_view(), name="serial_checker"),
	path("ip_prefix_checker/", views.IPPrefixCheckerView.as_view(), name="ip_prefix_checker"),
	path("prefix-validator/", views.PrefixValidatorView.as_view(), name="prefix_validator"),
	path("vm-ip-assigner/", views.VMIPAssignerView.as_view(), name="vm_ip_assigner"),
]
