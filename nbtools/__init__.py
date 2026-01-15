from netbox.plugins import PluginConfig
from django.db.models.signals import post_migrate
from .template_extensions import template_extensions

class NetboxToolsConfig(PluginConfig):
    name = "nbtools"  # Python module path
    verbose_name = "NetBox Tools"
    description = "Collection of tools for NetBox"
    version = "0.1.0"
    author = "Simon Möller Ahlquist"
    author_email = "simon.moller@lindab.com"
    license = "MIT"
    base_url = "nbtools"
    required_settings = []
    default_settings = {}
    top_level_menu = True



config = NetboxToolsConfig
print("DEBUG: nbtools plugin loaded successfully")
