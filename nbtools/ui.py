from netbox.plugins.ui import ObjectTab
from virtualization.models import VirtualMachine

class VirtualMachineCustomTab(ObjectTab):
    model = VirtualMachine
    label = "My Tab"
    permission = "virtualization.view_virtualmachine"
    template = "nbtools/vm_tab.html"

ui_components = [VirtualMachineCustomTab]
