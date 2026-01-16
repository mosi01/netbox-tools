from netbox.plugins import PluginTemplateExtension
from .models import DocumentationBinding

class VirtualMachinePanel(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        vm = self.context['object']  # Current VM object
        # Find document assigned to this VM by server_name
        document = DocumentationBinding.objects.filter(server_name=vm.name).first()
        if document:
            return self.render('nbtools/panel/vm_panel.html', extra_context={'document': document})
        return ''  # Hide panel if no document assigned

template_extensions = [VirtualMachinePanel]
