import logging

from django.shortcuts import render
from django.views import View

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ipaddress import ip_network
from ipam.models import Prefix, VRF

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class PrefixValidatorView(View):
    template_name = "nbtools/prefix_validator.html"

    def get(self, request):
        vrfs = VRF.objects.all()
        return render(request, self.template_name, {
            "vrfs": vrfs,
            "results": []
        })

    def post(self, request):
        vrfs = VRF.objects.all()
        results = []

        primary_id = request.POST.get("primary_vrf")
        secondary_id = request.POST.get("secondary_vrf")

        if primary_id and secondary_id:
            primary_prefixes = Prefix.objects.filter(vrf_id=primary_id).exclude(status__in=["container", "deprecated"])
            secondary_prefixes = Prefix.objects.filter(vrf_id=secondary_id).exclude(status__in=["container", "deprecated"])

            for pfx1 in primary_prefixes:
                net1 = ip_network(pfx1.prefix)
                active_overlaps = []
                reserved_overlaps = []

                for pfx2 in secondary_prefixes:
                    net2 = ip_network(pfx2.prefix)
                    if net1.overlaps(net2):
                        if pfx2.status == "reserved":
                            reserved_overlaps.append(f"{pfx2.prefix} (Reserved)")
                        else:
                            active_overlaps.append(f"{pfx2.prefix} ({pfx2.status.capitalize()})")

                results.append({
                    "prefix": f"{pfx1.prefix} ({pfx1.status.capitalize()})",
                    "active_overlaps": active_overlaps,
                    "reserved_overlaps": reserved_overlaps
                })

        return render(request, self.template_name, {
            "vrfs": vrfs,
            "results": results
        })