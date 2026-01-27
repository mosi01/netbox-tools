import logging

from django.shortcuts import render
from django.views import View

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ipaddress import ip_network
from ipam.models import Prefix, VRF, IPAddress

from django.contrib.contenttypes.models import ContentType


logger = logging.getLogger(__name__)

method_decorator(csrf_exempt, name='dispatch')
class IPPrefixCheckerView(View):
    template_name = "nbtools/ip_prefix_checker.html"

    def get(self, request):
        vrfs = VRF.objects.all()
        return render(request, self.template_name, {
            "vrfs": vrfs,
            "prefixes": [],
            "selected_vrf": None,
            "results": []
        })

    def post(self, request):
        vrfs = VRF.objects.all()
        prefixes = []
        results = []

        selected_vrf = request.POST.get("vrf")
        selected_prefix = request.POST.get("prefix")
        action = request.POST.get("action")
        skip_azure = bool(request.POST.get("azure"))

        if selected_vrf:
            prefixes = Prefix.objects.filter(vrf_id=selected_vrf)

        if action == "check_one" and selected_prefix:
            prefix_obj = Prefix.objects.get(id=selected_prefix)
            results = [self.calculate_prefix_stats(prefix_obj, skip_azure)]

        elif action == "check_all" and selected_vrf:
            results = [self.calculate_prefix_stats(pfx, skip_azure) for pfx in prefixes]

        return render(request, self.template_name, {
            "vrfs": vrfs,
            "prefixes": prefixes,
            "selected_vrf": selected_vrf,
            "results": results
        })

    def calculate_prefix_stats(self, prefix_obj, skip_azure=False):
        network = ip_network(prefix_obj.prefix)
        total_addresses = network.num_addresses

        assigned_ips = IPAddress.objects.filter(address__net_contained=prefix_obj.prefix)
        assigned_set = {str(ip.address.ip) for ip in assigned_ips}

        available_count = total_addresses - len(assigned_set)

        next_available = None
        hosts = list(network.hosts())
        start_index = 1 + (5 if skip_azure else 0)

        for ip in hosts[start_index:]:
            if str(ip) not in assigned_set:
                next_available = str(ip)
                break

        return {
            "prefix": prefix_obj.prefix,
            "url": prefix_obj.get_absolute_url(),
            "total": total_addresses,
            "available": available_count,
            "next": next_available or "None available"
        }