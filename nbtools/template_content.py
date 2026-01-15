from netbox.plugins import PluginTemplateExtension

class VirtualMachinePanel(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        return self.render('nbtools/virtualmachine_panel.html')

template_extensions = [VirtualMachinePanel]
