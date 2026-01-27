import logging

from django.shortcuts import render
from django.utils import timezone
from django.views import View
from datetime import date, timedelta
from django.db import transaction

from dcim.models import Device
from virtualization.models import VirtualMachine
from django.contrib import messages

import time

logger = logging.getLogger(__name__)

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
                logger.exception(f"Error preparing {str(obj)}: {e}")

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
                            "name": str(obj),
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