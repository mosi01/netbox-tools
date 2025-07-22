from netbox.plugins import PluginMenu, PluginMenuItem

menu = PluginMenu(
    label="NetBox Tools",
    icon_class="mdi mdi-tools",
    items=[
        PluginMenuItem(
            link="plugins:netbox_tools:dummy",
            link_text="Example Tool",
            permissions=["dcim.view_device"],
        ),
    ],
)

