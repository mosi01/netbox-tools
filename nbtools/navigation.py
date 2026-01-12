from netbox.plugins import PluginMenu, PluginMenuItem
from netbox.choices import ButtonColorChoices

menu = PluginMenu(
    label='NetBox Tools',
    icon_class='mdi mdi-tools',

    groups=(
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


        (
            'Infrastucture Tools',
            (
                PluginMenuItem(
                    link='plugins:nbtools:serial_checker',
                    link_text='Serial Number Checker',
                    auth_required=True,
                ),         
                PluginMenuItem(
                    link='plugins:nbtools:vm_ip_assigner',
                    link_text='(WIP)VM Tool',
                    auth_required=True,
                ),
            ),
        ),

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

            ),
        ),
        (
            'Documentation Tools',
            (
                PluginMenuItem(
                    link='plugins:nbtools:documentation_reviewer',
                    link_text='Documentation Reviewer',
                    auth_required=True,
                ),
            ),
        ),
    ),
)
