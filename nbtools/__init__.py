from netbox.plugins import PluginConfig

class NetboxToolsConfig(PluginConfig):
    name = "nbtools"
    verbose_name = "NetBox Tools"
    description = "Collection of tools for NetBox"
    version = "0.4.0"
    author = "Simon Möller Ahlquist"
    author_email = "simon.moller@lindab.com"
    license = "MIT"
    base_url = "nbtools"
    required_settings = []
    default_settings = {}
    top_level_menu = True

config = NetboxToolsConfig
