
"""
URL configuration for NetBox Tools plugin.
Maps views to their respective routes.
"""

from django.urls import path
from . import views

app_name = "nbtools"

urlpatterns = [
    # Dashboard view
    path("", views.dashboard, name="dashboard"),

    # Documentation Reviewer
    path("documentation-reviewer/", views.DocumentationReviewerView.as_view(), name="documentation_reviewer"),

    # Serial Number Checker
    path("serial-checker/", views.SerialChecker.as_view(), name="serial_checker"),

    # IP Prefix Checker
    path("ip_prefix_checker/", views.IPPrefixCheckerView.as_view(), name="ip_prefix_checker"),

    # Prefix Validator
    path("prefix-validator/", views.PrefixValidatorView.as_view(), name="prefix_validator"),

    # VM Tool
    path("vm-tool/", views.VMToolView.as_view(), name="vm_tool"),

    # Documentation Binding
    path("documentation-binding/", views.DocumentationBindingView.as_view(), name="documentation_binding"),
]
