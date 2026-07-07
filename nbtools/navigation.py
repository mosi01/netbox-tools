"""
Plugin navigation configuration for NetBox Tools.
Defines menu structure and items for the plugin.
"""

from netbox.plugins import PluginMenu, PluginMenuItem


menu = PluginMenu(
    label='NetBox Tools',
    icon_class='mdi mdi-tools',
    groups=(

        # -----------------------------
        # Dashboard group
        # -----------------------------
        (
            '',
            (
                PluginMenuItem(
                    link='plugins:nbtools:dashboard',
                    link_text='Dashboard',
                    auth_required=True,
                ),
            ),
        ),

        # -----------------------------
        # Infrastructure Tools group
        # -----------------------------
        (
            'Infrastructure Tools',
            (
                PluginMenuItem(
                    link='plugins:nbtools:serial_checker',
                    link_text='Serial Number Checker',
                    auth_required=True,
                ),
                PluginMenuItem(
                    link='plugins:nbtools:vm_tool',
                    link_text='VM Tool',
                    auth_required=True,
                ),
            ),
        ),

        # -----------------------------
        # Networking Tools group
        # -----------------------------
        (
            'Networking Tools',
            (
                PluginMenuItem(
                    link='plugins:nbtools:prefix_validator',
                    link_text='Prefix Validator',
                    auth_required=True,
                ),
                PluginMenuItem(
                    link='plugins:nbtools:ip_prefix_checker',
                    link_text='IP Prefix Checker',
                    auth_required=True,
                ),               
                PluginMenuItem(
                    link='plugins:nbtools:fortigate_policy_toolset',
                    link_text='Fortigate Policy Toolset',
                    auth_required=True,
                ),
                PluginMenuItem(
                    link='plugins:nbtools:fortiswitch_port_tool',
                    link_text='FortiSwitch Port Tool',
                    auth_required=True,
                ),
                PluginMenuItem(
                link="plugins:nbtools:fortiswitch_port_configuration_list",
                link_text="FortiSwitch Port Configurations",
                permissions=["nbtools.view_fortiswitchportconfiguration"],
                ),
                PluginMenuItem(
                    link='plugins:nbtools:fortisitebinding_list',
                    link_text='Forti Site Bindings',
                    auth_required=True,
                    permissions=['nbtools.view_fortisitebinding'],
                ),

            ),
        ),

        # -----------------------------
        # Documentation Tools group
        # -----------------------------
        (
            'Documentation Tools',
            (
                PluginMenuItem(
                    link='plugins:nbtools:documentation_reviewer',
                    link_text='Documentation Reviewer',
                    auth_required=True,
                ),
                PluginMenuItem(
                    link='plugins:nbtools:documentation_binding',
                    link_text='Documentation Binding',
                    auth_required=True,
                ),
            ),
        ),

        #  Commented out for main branch push
        # # ----------------------------------------------------
        # # NEW: Applications group (under Virtualization block)
        # # ----------------------------------------------------
        # (
        #     'Applications',
        #     (
        #         PluginMenuItem(
        #             link='plugins:nbtools:application_list',
        #             link_text='Applications',
        #             auth_required=True,
        #         ),
        #         PluginMenuItem(
        #             link='plugins:nbtools:service_list',
        #             link_text='Services',
        #             auth_required=True,
        #         ),
        #     ),
        # ),
    ),
)
