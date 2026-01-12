from django.shortcuts import render
from django.utils import timezone
from django.views import View
from datetime import date, timedelta
from django.db import transaction
from django.http import HttpResponse


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ipaddress import ip_network
from ipam.models import Prefix, VRF, IPAddress


from dcim.models import Device, DeviceRole, Site
from virtualization.models import VirtualMachine, Cluster, VMInterface
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages

import logging
import time
import re
logger = logging.getLogger("nbtools")

import re

def dashboard(request):

	context = {
		"device_count": Device.objects.count(),
		"vm_count": VirtualMachine.objects.count(),
	}

	return render(request, "nbtools/dashboard.html", context)




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





class DocumentationReviewerView(View):
    template_name = "nbtools/documentation_reviewer.html"
    cutoff_date = date(2025, 1, 1)

    def get(self, request):
        return self._render_page(request)

    def post(self, request):
        action = request.POST.get("action", "")
        search_query = request.POST.get("search", "").strip()

        try:
            if action == "mark_reviewed":
                self._mark_reviewed(request)

            elif action == "check_fields":
                self._check_fields()

        except Exception as e:
            logger.exception(f"Error in post action: {e}")

        return self._render_page(request, search_query)

    def _mark_reviewed(self, request):
        reviewed_ids = request.POST.getlist("reviewed_ids")
        logger.debug(f"Marking reviewed for IDs: {reviewed_ids}")

        count = 0
        today_iso = timezone.now().date().isoformat()
        for model in [Device, VirtualMachine]:
            for obj in model.objects.filter(pk__in=reviewed_ids):
                obj.custom_field_data["reviewed"] = True
                obj.custom_field_data["latest_update"] = today_iso
                obj.save()
                count += 1

        messages.success(request, f"{count} object{'s' if count != 1 else ''} marked as reviewed.")

    def _check_fields(self):
        for model in [Device, VirtualMachine]:
            queryset = model.objects.exclude(
                custom_field_data__has_key="latest_update"
            ).union(
                model.objects.exclude(custom_field_data__has_key="reviewed")
            )
            self._set_custom_fields_in_batches(queryset)

    def _set_custom_fields_in_batches(self, queryset):
        BATCH_SIZE = 100
        DELAY_BETWEEN_BATCHES = 0.5
        updates = []

        for obj in queryset:
            try:
                created_date = obj.created.date()
                capped_date = max(created_date, self.cutoff_date)

                obj.custom_field_data["latest_update"] = capped_date.isoformat()
                obj.custom_field_data["reviewed"] = created_date >= (timezone.now().date() - timedelta(days=90))

                updates.append(obj)
            except Exception as e:
                logger.exception(f"Error preparing {obj.name}: {e}")

        total = len(updates)
        logger.info(f"Starting batch update for {total} objects...")

        for i in range(0, total, BATCH_SIZE):
            batch = updates[i:i + BATCH_SIZE]
            try:
                with transaction.atomic():
                    for obj in batch:
                        obj.save()
                logger.info(f"Batch {i // BATCH_SIZE + 1}: Saved {len(batch)} objects")
            except Exception as e:
                logger.exception(f"Error saving batch {i // BATCH_SIZE + 1}: {e}")

            time.sleep(DELAY_BETWEEN_BATCHES)

        logger.info("Batch update complete.")

    def _render_page(self, request, search_query=""):
        flagged_objects = []
        valid_objects = 0
        missing_cf_data = False

        try:
            for model, label in [(Device, "Device"), (VirtualMachine, "Virtual Machine")]:
                queryset = model.objects.iterator()
                if search_query:
                    queryset = queryset.filter(name__icontains=search_query)

                for obj in queryset:
                    latest_update = obj.custom_field_data.get("latest_update")
                    reviewed = obj.custom_field_data.get("reviewed")

                    try:
                        outdated = date.fromisoformat(str(latest_update)) < self.cutoff_date
                    except Exception:
                        outdated = True

                    if latest_update and reviewed in [True, False]:
                        valid_objects += 1

                    if not latest_update or outdated or reviewed is not True:
                        flagged_objects.append({
                            "name": obj.name,
                            "type": label,
                            "latest_update": latest_update,
                            "reviewed": reviewed is True,
                            "id": obj.pk,
                            "url": obj.get_absolute_url()
                        })

            missing_cf_data = valid_objects == 0
        except Exception as e:
            logger.exception(f"Error building flagged list: {e}")

        message = ""
        if missing_cf_data:
            message = (
                "No documentation data found. Please define the custom fields "
                "`cf_latest_update` (Date) and `cf_reviewed` (Boolean) in NetBox for Devices and Virtual Machines. "
                "These fields are required for the Documentation Reviewer to function."
            )

        context = {
            "flagged_objects": flagged_objects,
            "search_query": search_query,
            "message": message,
        }

        return render(request, self.template_name, context)




class VMToolView(View):
    template_name = "nbtools/vm_tool.html"

    def get(self, request):
        return render(request, self.template_name, {
            "mode": "initial",
            "roles": DeviceRole.objects.all(),
            "sites": Site.objects.all(),
            "clusters": Cluster.objects.all(),
            "vms": VirtualMachine.objects.all(),
            "prefixes": Prefix.objects.all(),
        })

    def post(self, request):
        action = request.POST.get("action")

        if action == "cancel":
            return render(request, self.template_name, {"mode": "initial"})

        if action == "new_vm":
            return render(request, self.template_name, {
                "mode": "new_vm",
                "roles": DeviceRole.objects.all(),
                "sites": Site.objects.all(),
                "clusters": Cluster.objects.all(),
            })

        elif action == "create_vm":
            name = request.POST.get("name")
            role_id = request.POST.get("role")
            description = request.POST.get("description")
            site_id = request.POST.get("site")
            cluster_id = request.POST.get("cluster")

            try:
                if not name or not role_id or not site_id or not cluster_id:
                    raise ValueError("All required fields must be filled in.")
                vm = VirtualMachine.objects.create(
                    name=name, role_id=role_id, description=description,
                    site_id=site_id, cluster_id=cluster_id, status="active"
                )
                messages.success(request, f"VM '{vm.name}' created successfully!")
                return render(request, self.template_name, {"mode": "initial"})
            except Exception as e:
                messages.error(request, f"Failed to create VM: {e}")
                return render(request, self.template_name, {
                    "mode": "new_vm",
                    "roles": DeviceRole.objects.all(),
                    "sites": Site.objects.all(),
                    "clusters": Cluster.objects.all(),
                    "name": name, "description": description,
                    "role_id": role_id, "site_id": site_id, "cluster_id": cluster_id,
                })

        elif action == "existing_vm":
            return render(request, self.template_name, {
                "mode": "existing_vm",
                "vms": VirtualMachine.objects.all(),
                "prefixes": Prefix.objects.all(),
            })

        elif action == "apply_changes":
            vm_id = request.POST.get("vm")
            interface_id = request.POST.get("interface")
            prefix_id = request.POST.get("prefix")
            ip_address = request.POST.get("ip_address")
            auto_ip = request.POST.get("auto_ip") == "on"

            try:
                if not vm_id or not interface_id or not prefix_id:
                    raise ValueError("All required fields must be filled in.")
                if not auto_ip and not ip_address:
                    raise ValueError("Primary IP must be provided if auto IP is not selected.")

                vm = VirtualMachine.objects.get(id=vm_id)
                prefix = Prefix.objects.get(id=prefix_id)

                if interface_id == "new":
                    interface = VMInterface.objects.create(virtual_machine=vm, name=f"NIC-{vm.name}")
                else:
                    interface = VMInterface.objects.get(id=interface_id)

                if auto_ip:
                    network = ip_network(prefix.prefix)
                    assigned_ips = {str(ip.address.ip) for ip in IPAddress.objects.filter(address__net_contained=prefix.prefix)}
                    next_ip = next((str(host) for i, host in enumerate(network.hosts()) if i >= 5 and str(host) not in assigned_ips), None)
                    if not next_ip:
                        raise ValueError("No available IP found.")
                    ip_address = f"{next_ip}/32"
                else:
                    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_address):
                        raise ValueError("Invalid IP format.")
                    ip_address = f"{ip_address}/32"

                ip_obj = IPAddress.objects.create(address=ip_address)
                interface.ip_addresses.add(ip_obj)
                vm.primary_ip4 = ip_obj
                vm.save()

                messages.success(request, f'<a href="{vm.get_absolute_url()}">{vm.name}</a> was successfully updated and assigned to IP: {ip_address}', extra_tags="safe")
                return render(request, self.template_name, {"mode": "initial"})

            except Exception as e:
                messages.error(request, f"Failed to apply changes: {e}")
                return render(request, self.template_name, {
                    "mode": "existing_vm",
                    "vms": VirtualMachine.objects.all(),
                    "prefixes": Prefix.objects.all(),
                    "selected_vm": vm_id,
                    "selected_interface": interface_id,
                    "selected_prefix": prefix_id,
                    "ip_address": ip_address,
                })

        return render(request, self.template_name, {"mode": "initial"})



class SerialChecker(View):
    template_name = 'nbtools/serial_checker.html'

    def get(self, request):
        # Refresh everything on page load
        return self._render_page(request, index=0, refresh=True, show_list=False)

    def post(self, request):
        # Get index from form
        try:
            index = int(request.POST.get("index", 0))
        except ValueError:
            index = 0

        # Determine which button was pressed
        if "next" in request.POST:
            action = "next"
        elif "show_list" in request.POST:
            action = "show_list"
        else:
            action = "check"

        refresh = action == "check"
        show_list = action == "show_list"

        # Increment index if "next" was pressed
        if action == "next":
            index += 1

        return self._render_page(request, index=index, refresh=refresh, show_list=show_list)

    def _render_page(self, request, index, refresh, show_list):
        pattern = re.compile(r'^[A-Z]{2}\d{2,3}[A-Z]{3,5}(\d{4})$')
        all_numbers = [f"{i:04d}" for i in range(1, 10000)]

        # Refresh data or load from session
        if refresh or "taken_map" not in request.session:
            taken_map = {}
            for vm in VirtualMachine.objects.only("name"):
                match = pattern.match(vm.name)
                if match:
                    serial = match.group(1)
                    taken_map[serial] = vm.name

            taken_ints = sorted(int(s) for s in taken_map.keys())
            lowest_taken = taken_ints[0] if taken_ints else 0
            highest_taken = taken_ints[-1] if taken_ints else 0

            available_numbers = [
                n for n in all_numbers
                if n not in taken_map and int(n) > highest_taken
            ]

            # Save to session
            request.session["taken_map"] = taken_map
            request.session["available_numbers"] = available_numbers
            request.session["lowest_taken"] = lowest_taken
            request.session["highest_taken"] = highest_taken
        else:
            taken_map = request.session.get("taken_map", {})
            available_numbers = request.session.get("available_numbers", [])
            lowest_taken = request.session.get("lowest_taken", 0)
            highest_taken = request.session.get("highest_taken", 0)

        # Wrap index
        if index >= len(available_numbers):
            index = 0

        next_number = available_numbers[0] if available_numbers else "None"
        preview_number = available_numbers[index] if available_numbers else "None"

        # Build list table if requested
        list_table = []
        if show_list:
            start = lowest_taken
            end = min(highest_taken + 1000, 9999)
            for i in range(start, end + 1):
                serial = f"{i:04d}"
                list_table.append({
                    "serial": serial,
                    "name": taken_map.get(serial, "Available")
                })

        context = {
            "next_number": next_number,
            "preview_number": preview_number,
            "index": index,
            "available_count": len(available_numbers),
            "taken_count": len(taken_map),
            "total_count": len(all_numbers),
            "show_list": show_list,
            "list_table": list_table,
            "lowest_taken": f"{lowest_taken:04d}",
            "highest_taken": f"{highest_taken:04d}",
        }

        return render(request, self.template_name, context)




