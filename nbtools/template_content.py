
from netbox.plugins import PluginTemplateExtension

# -------------------------------
# Documentation Tab for Virtual Machines
# -------------------------------
class VirtualMachineDocsTab(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'
    tab = 'Documentation'  # Creates a new tab on the VM detail page

    def render(self, request):
        # Debug logging to confirm injection
        vm = self.context['object']
        print(f"DEBUG: Injecting Documentation tab for VM {vm.name}")

        from .models import DocumentationBinding
        docs = DocumentationBinding.objects.filter(server_name__iexact=vm.name, category="Server")

        # Debug logging for document count
        print(f"DEBUG: Found {docs.count()} documents for VM {vm.name}")

        return self.render('nbtools/Tabs/vm_docs_box.html', extra_context={'docs': docs})


# -------------------------------
# Documentation Tab for Devices / Applications
# -------------------------------
class ApplicationDocsTab(PluginTemplateExtension):
    model = 'dcim.device'
    tab = 'Documentation'  # Creates a new tab on the Device detail page

    def render(self, request):
        # Debug logging to confirm injection
        device = self.context['object']
        print(f"DEBUG: Injecting Documentation tab for Device {device.name}")

        from .models import DocumentationBinding
        docs = DocumentationBinding.objects.filter(application_name__iexact=device.name, category="Application")

        # Debug logging for document count
        print(f"DEBUG: Found {docs.count()} documents for Device {device.name}")

        return self.render('nbtools/Tabs/app_docs_box.html', extra_context={'docs': docs})


# -------------------------------
# Fallback Test Tab
# -------------------------------
class TestTab(PluginTemplateExtension):
    model = 'virtualization.virtualmachine'
    tab = 'TestTab'  # Simple test tab to confirm plugin injection works

    def render(self, request):
        print("DEBUG: Injecting TestTab for VM page")
        return "<h1>Test Tab Works!</h1>"


# Register all template extensions
template_extensions = [VirtualMachineDocsTab, ApplicationDocsTab, TestTab]
