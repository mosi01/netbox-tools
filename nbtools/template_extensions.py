from netbox.plugins import PluginTemplateExtension

class VirtualMachineDocsExtension(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'

    def right_page(self):
        from .models import DocumentationBinding  # Lazy import
        vm = self.context['object']
        docs = DocumentationBinding.objects.filter(server_name__iexact=vm.name, category="Server")
        return self.render('nbtools/Panels/vm_docs_box.html', extra_context={'docs': docs})

class ApplicationDocsExtension(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'  # Or your custom Application model if you have one

    def right_page(self):
        from .models import DocumentationBinding  # Lazy import
        device = self.context['object']
        docs = DocumentationBinding.objects.filter(application_name__iexact=device.name, category="Application")
        return self.render('nbtools/Panels/app_docs_box.html', extra_context={'docs': docs})

template_extensions = [VirtualMachineDocsExtension, ApplicationDocsExtension]
