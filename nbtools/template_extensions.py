from netbox.plugins import PluginTemplateExtension
from .models import DocumentationBinding

class VMDocumentationExtension(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        vm = self.context['object']
        docs = DocumentationBinding.objects.filter(server_name=vm.name)
        return self.render('nbtools/vm_docs_box.html', extra_context={'docs': docs})

class ApplicationDocumentationExtension(PluginTemplateExtension):
    model = 'dcim.device'  # Assuming applications are represented as devices or custom model
    def right_page(self):
        app = self.context['object']
        docs = DocumentationBinding.objects.filter(application_name=app.name)
        return self.render('nbtools/app_docs_box.html', extra_context={'docs': docs})

template_extensions = [VMDocumentationExtension, ApplicationDocumentationExtension]
