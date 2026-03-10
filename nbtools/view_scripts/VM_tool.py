from django.shortcuts import render
from django.views import View
from django.db import transaction

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ipaddress import ip_network
from ipam.models import Prefix, VRF, IPAddress

from dcim.models import Device, DeviceRole, Site
from virtualization.models import VirtualMachine, Cluster, VMInterface

import logging
import re


logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class VMToolView(View):
    template_name = "nbtools/vm_tool.html"

    def get(self, request):
        return render(request, self.template_name, {
            "mode": "initial",
            "roles": DeviceRole.objects.all(),
            "sites": Site.objects.all(),
            "clusters": Cluster.objects.all(),
            "vms": VirtualMachine.objects.all(),
            "vrfs": VRF.objects.all(),
            "prefixes": [],
            "popup_message": "",
            "info_message": "",
            "error_message": ""
        })

    def post(self, request):
        action = request.POST.get("action")

        if action == "cancel":
            return render(request, self.template_name, {"mode": "initial", "popup_message": "", "info_message": "", "error_message": ""})

        if action == "new_vm":
            return render(request, self.template_name, {
                "mode": "new_vm",
                "roles": DeviceRole.objects.all(),
                "sites": Site.objects.all(),
                "clusters": Cluster.objects.all(),
                "popup_message": "",
                "info_message": "",
                "error_message": ""
            })

        if action == "create_vm":
            return self.create_vm(request)

        if action == "apply_changes":
            return self.apply_changes(request)

        return self.handle_existing_vm(request)

    def create_vm(self, request):
        name = request.POST.get("name")
        role_id = request.POST.get("role")
        description = request.POST.get("description")
        site_id = request.POST.get("site")
        cluster_id = request.POST.get("cluster")

        try:
            if not name or not role_id or not site_id or not cluster_id:
                raise ValueError("All required fields must be filled in.")

            vm = VirtualMachine.objects.create(
                name=name,
                role_id=role_id,
                description=description,
                site_id=site_id,
                cluster_id=cluster_id,
                status="active"
            )

            popup_message = f'{vm.name} created successfully!'
            return render(request, self.template_name, {"mode": "initial", "popup_message": popup_message, "info_message": "", "error_message": ""})

        except Exception as e:
            return render(request, self.template_name, {
                "mode": "new_vm",
                "roles": DeviceRole.objects.all(),
                "sites": Site.objects.all(),
                "clusters": Cluster.objects.all(),
                "name": name,
                "description": description,
                "role_id": role_id,
                "site_id": site_id,
                "cluster_id": cluster_id,
                "popup_message": "",
                "info_message": "",
                "error_message": f"Failed to create VM: {e}"
            })

    def handle_existing_vm(self, request, error_message=""):
        vm_id = request.POST.get("vm")
        interface_id = request.POST.get("interface")
        selected_vrf = request.POST.get("vrf")
        prefix_id = request.POST.get("prefix")
        ip_address_display = request.POST.get("ip_address")
        auto_ip = request.POST.get("auto_ip") == "on"

        interfaces = []
        selected_prefix = None
        info_message = ""

        if vm_id:
            try:
                vm = VirtualMachine.objects.get(id=vm_id)
                interfaces = list(vm.interfaces.all())

                if interface_id and interface_id != "new":
                    iface = VMInterface.objects.get(id=interface_id)
                    if iface.ip_addresses.exists():
                        ip_obj = iface.ip_addresses.first()
                        ip_address_display = str(ip_obj.address.ip)

                        prefix_obj = Prefix.objects.filter(
                            prefix__net_contains=ip_obj.address,
                            status__in=["active", "reserved"]
                        ).first()
                        if prefix_obj:
                            selected_prefix = str(prefix_obj.id)
                            selected_vrf = str(prefix_obj.vrf.id)

                        info_message = f"For the selected NIC, fetched Primary IP: {ip_address_display}, VRF: {prefix_obj.vrf.name if prefix_obj else 'None'}, IP Prefix: {prefix_obj.prefix if prefix_obj else 'None'}"
            except VirtualMachine.DoesNotExist:
                interfaces = []

        prefixes = []
        if selected_vrf:
            prefixes = Prefix.objects.filter(vrf_id=selected_vrf, status__in=["active", "reserved"])
        elif selected_prefix:
            prefixes = Prefix.objects.filter(id=selected_prefix)

        return render(request, self.template_name, {
            "mode": "existing_vm",
            "vms": VirtualMachine.objects.all(),
            "vrfs": VRF.objects.all(),
            "prefixes": prefixes,
            "interfaces": interfaces,
            "selected_vm": vm_id,
            "selected_interface": interface_id,
            "selected_vrf": selected_vrf,
            "selected_prefix": selected_prefix or prefix_id,
            "ip_address": ip_address_display,
            "auto_ip": auto_ip,
            "popup_message": "",
            "info_message": info_message,
            "error_message": error_message
        })

    def apply_changes(self, request):
        vm_id = request.POST.get("vm")
        interface_id = request.POST.get("interface")
        prefix_id = request.POST.get("prefix")
        ip_address = request.POST.get("ip_address", "").strip()
        auto_ip = request.POST.get("auto_ip") == "on"
        selected_vrf = request.POST.get("vrf")

        try:
            if not vm_id or not prefix_id:
                raise ValueError("VM and Prefix must be selected.")
            if not auto_ip and not ip_address:
                raise ValueError("Primary IP must be provided if auto IP is not selected.")
            if not auto_ip and not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_address):
                raise ValueError("Invalid IP format.")

            vm = VirtualMachine.objects.get(id=vm_id)
            prefix = Prefix.objects.get(id=prefix_id)

            if not interface_id or interface_id == "new":
                interface = VMInterface.objects.create(virtual_machine=vm, name=f"NIC-{vm.name}")
            else:
                interface = VMInterface.objects.get(id=interface_id)

            if interface.ip_addresses.exists():
                interface.ip_addresses.clear()

            if auto_ip:
                network = ip_network(prefix.prefix)
                assigned_ips = {str(ip.address.ip) for ip in IPAddress.objects.filter(address__net_contained=prefix.prefix)}
                next_ip = next((str(host) for i, host in enumerate(network.hosts()) if i >= 5 and str(host) not in assigned_ips), None)
                if not next_ip:
                    raise ValueError("No available IP found.")
                ip_address = f"{next_ip}/32"
            else:
                ip_address = f"{ip_address}/32"

            with transaction.atomic():
                ip_obj = IPAddress.objects.create(address=ip_address, vrf_id=selected_vrf)
                interface.ip_addresses.add(ip_obj)
                vm.primary_ip4 = ip_obj
                vm.save()

            popup_message = f'{vm.name} was successfully updated and assigned to IP: {ip_address}'
            return render(request, self.template_name, {"mode": "initial", "popup_message": popup_message, "info_message": "", "error_message": ""})

        except Exception as e:
            return self.handle_existing_vm(request, error_message=str(e))