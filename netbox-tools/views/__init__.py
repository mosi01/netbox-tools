from django.views.generic import TemplateView

class DummyView(TemplateView):
    template_name = "netbox_tools/base.html"
