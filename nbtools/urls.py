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
    path(
        "documentation-reviewer/",
        views.DocumentationReviewerView.as_view(),
        name="documentation_reviewer",
    ),

    # Serial Number Checker
    path(
        "serial-checker/",
        views.SerialChecker.as_view(),
        name="serial_checker",
    ),

    # IP Prefix Checker
    path(
        "ip_prefix_checker/",
        views.IPPrefixCheckerView.as_view(),
        name="ip_prefix_checker",
    ),

    # Prefix Validator
    path(
        "prefix-validator/",
        views.PrefixValidatorView.as_view(),
        name="prefix_validator",
    ),

    # VM Tool
    path(
        "vm-tool/",
        views.VMToolView.as_view(),
        name="vm_tool",
    ),

    # Documentation Binding
    path(
        "documentation-binding/",
        views.DocumentationBindingView.as_view(),
        name="documentation_binding",
    ),

    # -----------------------------------------------------------------------
    # Applications & Services
    # -----------------------------------------------------------------------

    # Applications list + detail + add + edit
    path(
        "applications/",
        views.ApplicationListView.as_view(),
        name="application_list",
    ),
    path(
        "applications/add/",
        views.ApplicationEditView.as_view(),
        name="application_add",
    ),
    path(
        "applications/<int:pk>/",
        views.ApplicationDetailView.as_view(),
        name="application_detail",
    ),
    path(
        "applications/<int:pk>/edit/",
        views.ApplicationEditView.as_view(),
        name="application_edit",
    ),

    # Services list + detail + add + edit
    path(
        "services/",
        views.ServiceListView.as_view(),
        name="service_list",
    ),
    path(
        "services/add/",
        views.ServiceEditView.as_view(),
        name="service_add",
    ),
    path(
        "services/<int:pk>/",
        views.ServiceDetailView.as_view(),
        name="service_detail",
    ),
    path(
        "services/<int:pk>/edit/",
        views.ServiceEditView.as_view(),
        name="service_edit",
    ),
]