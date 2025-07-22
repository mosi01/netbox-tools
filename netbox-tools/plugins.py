from netbox.plugins import PluginConfig

class NetBoxToolsConfig(PluginConfig):
    name = "netbox_tools"
    verbose_name = "NetBox Tools"
    version = "0.2"
    base_url = "tools"
    default_urls = "netbox_tools.urls"
    navigation = "netbox_tools.navigation.menu"

config = NetBoxToolsConfig

