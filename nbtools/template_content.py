from netbox.plugins import PluginTemplateExtension
from .models import DocumentationBinding

class VirtualMachinePanel(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        obj = self.context.get('object')
        documents = DocumentationBinding.objects.filter(server_name=str(obj)).order_by('category', 'file_name')
        
        if documents.exists():
            grouped_docs = {}
            for doc in documents:
                grouped_docs.setdefault(doc.category, []).append(doc)
            return self.render('nbtools/panels/vm_panel.html', extra_context={'grouped_docs': grouped_docs})
        return ''

template_extensions = [VirtualMachinePanel]
