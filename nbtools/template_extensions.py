
from netbox.plugins import PluginTemplateExtension

class VirtualMachineDocsTab(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'
    tab = 'Documentation'  # This creates a new tab on the VM detail page

    def render(self):
        from .models import DocumentationBinding  # Lazy import to avoid AppRegistryNotReady
        vm = self.context['object']
        docs = DocumentationBinding.objects.filter(server_name__iexact=vm.name, category="Server")
        return self.render('nbtools/Tabs/vm_docs_box.html', extra_context={'docs': docs})


class ApplicationDocsTab(PluginTemplateExtension):
    model = 'dcim.device'  # Or your custom Application model if you have one
    tab = 'Documentation'  # Creates a new tab on the Device/Application detail page

    def render(self):
        from .models import DocumentationBinding
        device = self.context['object']
        docs = DocumentationBinding.objects.filter(application_name__iexact=device.name, category="Application")
        return self.render('nbtools/Tabs/app_docs_box.html', extra_context={'docs': docs})


# Register both template extensions
template_extensions = [VirtualMachineDocsTab, ApplicationDocsTab]
