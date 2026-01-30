from netbox.plugins import PluginConfig

class NetboxToolsConfig(PluginConfig):
    name = "nbtools"
    verbose_name = "NetBox Tools"
    description = "Collection of tools for NetBox"
    version = "1.1.0"
    min_version = "4.5.0"
    max_version = "4.5.99"
    author = "Simon Möller Ahlquist"
    author_email = "simon.moller@lindab.com"
    license = "MIT"
    base_url = "nbtools"
    api_urls = "nbtools.api.urls"
    required_settings = []
    default_settings = {}
    top_level_menu = True

config = NetboxToolsConfig
