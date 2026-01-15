from netbox.plugins.ui import ObjectSidebarPanel

class VirtualMachineSidebarPanel(ObjectSidebarPanel):
    # Target model
    model = 'virtualization.virtualmachine'
    # Template to render
    template = 'my_plugin/vm_sidebar_panel.html'
    # Panel title
    label = 'Custom Info'
    # Optional: position in sidebar
    weight = 100

# NetBox will auto-discover this list
ui_components = [VirtualMachineSidebarPanel]
