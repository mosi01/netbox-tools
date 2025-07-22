# NetBox Tools

A plugin for NetBox providing a set of helper views/tools such as:
- Devices without primary IPs
- Custom network utilities

## Requirements
- NetBox 4.3+
- Python 3.10+

## Installation
Clone this repo to `/opt/netbox/netbox/plugins/netbox_tools`, then:
```bash
cd /opt/netbox/netbox/plugins/netbox_tools
pip install -e .
```

Enable it in you `configuration.py`, with:
```bash
PLUGINS = ["netbox_tools"]
```
