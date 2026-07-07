"""
urls.py

NetBox 4.5.x / 4.6.x plugin URL patterns for nbtools.
"""

from django.urls import path

from . import views

app_name = "nbtools"

urlpatterns = [
    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    path("", views.dashboard, name="dashboard"),

    # ------------------------------------------------------------------
    # Documentation Reviewer
    # ------------------------------------------------------------------
    path(
        "documentation-reviewer/",
        views.DocumentationReviewerView.as_view(),
        name="documentation_reviewer",
    ),

    # ------------------------------------------------------------------
    # Serial Number Checker
    # ------------------------------------------------------------------
    path(
        "serial-checker/",
        views.SerialChecker.as_view(),
        name="serial_checker",
    ),

    # ------------------------------------------------------------------
    # IP Prefix Checker
    # ------------------------------------------------------------------
    path(
        "ip_prefix_checker/",
        views.IPPrefixCheckerView.as_view(),
        name="ip_prefix_checker",
    ),

    # ------------------------------------------------------------------
    # Prefix Validator
    # ------------------------------------------------------------------
    path(
        "prefix-validator/",
        views.PrefixValidatorView.as_view(),
        name="prefix_validator",
    ),

    # ------------------------------------------------------------------
    # FortiGate Policy Toolset
    # ------------------------------------------------------------------
    path(
        "fortigate-policy-toolset/",
        views.FortigatePolicyToolsetView.as_view(),
        name="fortigate_policy_toolset",
    ),

    # ------------------------------------------------------------------
    # FortiSwitch Port Tool (bulk-capable custom page)
    # ------------------------------------------------------------------
    path(
        "fortiswitch-port-tool/",
        views.FortiSwitchPortToolView.as_view(),
        name="fortiswitch_port_tool",
    ),

       
    # ------------------------------------------------------------------
    # FortiSwitch Port Configuration
    # ------------------------------------------------------------------     
    path(
        "fortiswitch-port-configurations/",
        views.FortiSwitchPortConfigurationListView.as_view(),
        name="fortiswitchportconfiguration_list",
    ),
    path(
        "fortiswitch-port-configurations/<int:pk>/",
        views.FortiSwitchPortConfigurationView.as_view(),
        name="fortiswitchportconfiguration",
    ),
    path(
        "fortiswitch-port-configurations/add/",
        views.FortiSwitchPortConfigurationEditView.as_view(),
        name="fortiswitchportconfiguration_add",
    ),
    path(
        "fortiswitch-port-configurations/<int:pk>/edit/",
        views.FortiSwitchPortConfigurationEditView.as_view(),
        name="fortiswitchportconfiguration_edit",
    ),
    path(
        "fortiswitch-port-configurations/<int:pk>/delete/",
        views.FortiSwitchPortConfigurationDeleteView.as_view(),
        name="fortiswitchportconfiguration_delete",
    ),
    path(
        "fortiswitch-port-configurations/<int:pk>/changelog/",
        views.FortiSwitchPortConfigurationChangeLogView.as_view(),
        name="fortiswitchportconfiguration_changelog",
    ),

    
    
    # ------------------------------------------------------------------
    # FortiSiteBinding CRUD + changelog
    # ------------------------------------------------------------------
    path(
        "forti-bindings/",
        views.FortiSiteBindingListView.as_view(),
        name="fortisitebinding_list",
    ),
    path(
        "forti-bindings/add/",
        views.FortiSiteBindingEditView.as_view(),
        name="fortisitebinding_add",
    ),
    path(
        "forti-bindings/<int:pk>/",
        views.FortiSiteBindingView.as_view(),
        name="fortisitebinding",
    ),
    path(
        "forti-bindings/<int:pk>/edit/",
        views.FortiSiteBindingEditView.as_view(),
        name="fortisitebinding_edit",
    ),
    path(
        "forti-bindings/<int:pk>/delete/",
        views.FortiSiteBindingDeleteView.as_view(),
        name="fortisitebinding_delete",
    ),
    path(
        "forti-bindings/<int:pk>/changelog/",
        views.FortiSiteBindingChangeLogView.as_view(),
        name="fortisitebinding_changelog",
    ),

    # ------------------------------------------------------------------
    # VM Tool
    # ------------------------------------------------------------------
    path(
        "vm-tool/",
        views.VMToolView.as_view(),
        name="vm_tool",
    ),

    # ------------------------------------------------------------------
    # Documentation Binding
    # ------------------------------------------------------------------
    path(
        "documentation-binding/",
        views.DocumentationBindingView.as_view(),
        name="documentation_binding",
    ),
]
