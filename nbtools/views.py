#Django Imports
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.urls import reverse

#Netbox Imports
from dcim.models import Device
from virtualization.models import VirtualMachine
from ipam.models import Prefix, VRF
from ipam.choices import PrefixStatusChoices

#Sys imports
from datetime import date, timedelta
import ipaddress
import logging
import time
import re

logger = logging.getLogger("nbtools")



def dashboard(request):
	
	context = {
		"device_count": Device.objects.count(),
		"vm_count": VirtualMachine.objects.count(),
	}

	return render(request, "nbtools/dashboard.html", context)

def documentation_reviewer(request):
    valid_objects = 0
    flagged_objects = []
    reviewed_ids = []
    message = ""
    search_query = request.POST.get("search", "").strip()
    action = request.POST.get("action", "")
    cutoff_date = date(2025, 1, 1)

    try:
        # Action: Mark Reviewed
        if action == "mark_reviewed":
            reviewed_ids = request.POST.getlist("reviewed_ids")
            logger.debug(f"Marking reviewed for IDs: {reviewed_ids}")

            count = 0
            for model in [Device, VirtualMachine]:
                for obj in model.objects.filter(pk__in=reviewed_ids):
                    obj.custom_field_data["reviewed"] = True
                    obj.save()
                    count += 1

            messages.success(request, f"{count} object{'s' if count != 1 else ''} marked as reviewed.")

        # Action: Check Fields
        if action == "check_fields":
            def set_custom_fields_in_batches(queryset, cutoff_date):
                BATCH_SIZE = 100
                DELAY_BETWEEN_BATCHES = 0.5
                updates = []

                for obj in queryset:
                    try:
                        created_date = obj.created.date()
                        capped_date = max(created_date, cutoff_date)
                        obj.custom_field_data["latest_update"] = capped_date.isoformat()
                        obj.custom_field_data["reviewed"] = created_date >= (timezone.now().date() - timedelta(days=90))
                        updates.append(obj)
                    except Exception as e:
                        logger.exception(f"Error preparing {obj.name}: {e}")

                for i in range(0, len(updates), BATCH_SIZE):
                    batch = updates[i:i + BATCH_SIZE]
                    try:
                        with transaction.atomic():
                            for obj in batch:
                                obj.save()
                        logger.info(f"Batch {i // BATCH_SIZE + 1}: Saved {len(batch)} objects")
                    except Exception as e:
                        logger.exception(f"Error saving batch {i // BATCH_SIZE + 1}: {e}")
                    time.sleep(DELAY_BETWEEN_BATCHES)

            for model in [Device, VirtualMachine]:
                queryset = model.objects.exclude(custom_field_data__has_key="latest_update").union(
                    model.objects.exclude(custom_field_data__has_key="reviewed")
                )
                set_custom_fields_in_batches(queryset, cutoff_date)

        # Refresh flagged list
        for model, label in [(Device, "Device"), (VirtualMachine, "Virtual Machine")]:
            queryset = model.objects.all()
            if search_query:
                queryset = queryset.filter(name__icontains=search_query)

            for obj in queryset:
                latest_update = obj.custom_field_data.get("latest_update")
                reviewed = obj.custom_field_data.get("reviewed")

                try:
                    outdated = date.fromisoformat(str(latest_update)) < cutoff_date
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

        if valid_objects == 0:
            message = (
                "No documentation data found. Please define the custom fields "
                "`cf_latest_update` (Date) and `cf_reviewed` (Boolean) in NetBox for Devices and Virtual Machines. "
                "These fields are required for the Documentation Reviewer to function."
            )

    except Exception as e:
        logger.exception(f"Error in documentation_reviewer view: {e}")
        message = "An unexpected error occurred while processing your request."

    context = {
        "flagged_objects": flagged_objects,
        "search_query": search_query,
        "message": message,
        "reviewed_ids": reviewed_ids,
    }

    return render(request, "nbtools/documentation_reviewer.html", context)



def prefix_validator_view(request):
    integration_vrf_id = request.GET.get("integration_vrf")
    main_vrf_id = request.GET.get("main_vrf")
    results = []

    if integration_vrf_id and main_vrf_id:
        integration_prefixes = Prefix.objects.filter(
            vrf_id=integration_vrf_id,
            status__in=[
                PrefixStatusChoices.STATUS_ACTIVE,
                PrefixStatusChoices.STATUS_RESERVED
            ]
        )
        main_prefixes = Prefix.objects.filter(
            vrf_id=main_vrf_id,
            status__in=[
                PrefixStatusChoices.STATUS_ACTIVE,
                PrefixStatusChoices.STATUS_RESERVED
            ]
        )

        for ipfx in integration_prefixes:
            for mpfx in main_prefixes:
                # Check for overlap using containment
                if ipfx.prefix in mpfx.prefix or mpfx.prefix in ipfx.prefix:
                    results.append({
                        "prefix": str(ipfx.prefix),
                        "message": f"Overlaps with {mpfx.prefix}",
                        "color": "danger"
                    })
                    break  # Stop after first overlap
            else:
                results.append({
                    "prefix": str(ipfx.prefix),
                    "message": "No overlap",
                    "color": "success"
                })

    context = {
        "vrfs": VRF.objects.all(),
        "integration_vrf_id": integration_vrf_id,
        "main_vrf_id": main_vrf_id,
        "results": results
    }
    return render(request, "nbtools/prefix_validator.html", context)



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

