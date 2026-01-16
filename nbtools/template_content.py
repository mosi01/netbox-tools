from netbox.plugins import PluginTemplateExtension
from .models import DocumentationBinding

class VirtualMachinePanel(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        vm = self.context['object']  # Current VM object
        # Fetch all documents assigned to this VM
        documents = DocumentationBinding.objects.filter(server_name=vm.name).order_by('category', 'file_name')

        if documents.exists():
            # Group documents by category
            grouped_docs = {}
            for doc in documents:
                grouped_docs.setdefault(doc.category, []).append(doc)

            return self.render('nbtools/panels/vm_panel.html', extra_context={'grouped_docs': grouped_docs})
        return ''  # Hide panel if no document assigned

template_extensions = [VirtualMachinePanel]
