import logging
import time
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from dcim.models import Device
from virtualization.models import VirtualMachine
from extras.models import CustomField

logger = logging.getLogger(__name__)


class DocumentationReviewerView(View):
    template_name = "nbtools/documentation_reviewer.html"
    # Anything before this date is considered outdated documentation
    cutoff_date = date(2025, 1, 1)

    #
    # HTTP handlers
    #

    def get(self, request):
        # Ensure custom fields exist every time the page is loaded
        self._ensure_custom_fields()
        return self._render_page(request)

    def post(self, request):
        action = request.POST.get("action", "")
        search_query = request.POST.get("search", "").strip()

        # Ensure custom fields exist before doing anything else
        self._ensure_custom_fields()

        try:
            if action == "mark_reviewed":
                self._mark_reviewed(request)
            elif action in ("check_fields", "update_fields"):
                # Treat "Check Fields" and "Update Fields" as the same action
                self._check_fields()
        except Exception as e:
            logger.exception(f"Error in post action: {e}")

        return self._render_page(request, search_query)

    #
    # CustomField helpers
    #

    def _ensure_custom_fields(self):
        """
        Ensure that the required custom fields exist in NetBox for
        Device and VirtualMachine objects. If they don't exist, create them.

        Fields:
          - latest_update (Date)
          - reviewed (Boolean)
        """
        logger.debug("Ensuring required custom fields exist...")

        device_ct = ContentType.objects.get_for_model(Device)
        vm_ct = ContentType.objects.get_for_model(VirtualMachine)
        object_types = [device_ct, vm_ct]

        field_defs = [
            {
                "name": "latest_update",
                "label": "Latest Update",
                "type": "date",
            },
            {
                "name": "reviewed",
                "label": "Reviewed",
                "type": "boolean",
            },
        ]

        for fd in field_defs:
            cf, created = CustomField.objects.get_or_create(
                name=fd["name"],
                defaults={
                    "label": fd["label"],
                    "type": fd["type"],
                    "group_name": "Review",
                    "search_weight": 1000,
                    "filter_logic": "loose",
                    "ui_visible": True,
                    "ui_editable": True,
                    "weight": 100,
                    "is_cloneable": False,
                },
            )

            if created:
                logger.info(f"Created custom field '{cf.name}'")
            else:
                logger.debug(f"Custom field '{cf.name}' already exists")

            # Ensure correct object types are assigned
            current_ots = set(cf.object_types.all())
            desired_ots = set(object_types)
            if current_ots != desired_ots:
                cf.object_types.set(object_types)
                cf.save()
                logger.info(
                    f"Updated object types for custom field '{cf.name}' "
                    f"to Device and VirtualMachine"
                )

    #
    # Actions
    #

    def _mark_reviewed(self, request):
        reviewed_ids = request.POST.getlist("reviewed_ids")
        logger.debug(f"Marking reviewed for IDs: {reviewed_ids}")

        count = 0
        today_iso = timezone.now().date().isoformat()

        for model in [Device, VirtualMachine]:
            for obj in model.objects.filter(pk__in=reviewed_ids):
                # Use the custom field names (not cf_* prefix)
                obj.custom_field_data["reviewed"] = True
                obj.custom_field_data["latest_update"] = today_iso
                obj.save()
                count += 1

        messages.success(
            request,
            f"{count} object{'s' if count != 1 else ''} marked as reviewed.",
        )

    def _check_fields(self):
        """
        For all Devices/VMs that don't have the custom field keys yet,
        set sensible defaults in batches.
        """
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
                # cap "latest_update" at the cutoff date
                capped_date = max(created_date, self.cutoff_date)
                obj.custom_field_data["latest_update"] = capped_date.isoformat()
                # mark reviewed if created within the last 90 days
                obj.custom_field_data["reviewed"] = created_date >= (
                    timezone.now().date() - timedelta(days=90)
                )
                updates.append(obj)
            except Exception as e:
                logger.exception(f"Error preparing {str(obj)}: {e}")

        total = len(updates)
        logger.info(f"Starting batch update for {total} objects...")

        for i in range(0, total, BATCH_SIZE):
            batch = updates[i : i + BATCH_SIZE]
            try:
                with transaction.atomic():
                    for obj in batch:
                        obj.save()
                logger.info(
                    f"Batch {i // BATCH_SIZE + 1}: "
                    f"Saved {len(batch)} objects"
                )
            except Exception as e:
                logger.exception(
                    f"Error saving batch {i // BATCH_SIZE + 1}: {e}"
                )
            time.sleep(DELAY_BETWEEN_BATCHES)

        logger.info("Batch update complete.")

    #
    # Rendering
    #

    def _render_page(self, request, search_query=""):
        flagged_objects = []
        valid_objects = 0
        missing_cf_data = False

        try:
            for model, label in [(Device, "Device"), (VirtualMachine, "Virtual Machine")]:
                # Use a queryset we *can* filter on
                queryset = model.objects.all()
                if search_query:
                    queryset = queryset.filter(name__icontains=search_query)

                for obj in queryset.iterator():
                    latest_update = obj.custom_field_data.get("latest_update")
                    reviewed = obj.custom_field_data.get("reviewed")

                    try:
                        outdated = date.fromisoformat(str(latest_update)) < self.cutoff_date
                    except Exception:
                        outdated = True

                    # "Valid" here means: both fields exist
                    if latest_update and reviewed in [True, False]:
                        valid_objects += 1

                    # Flag if missing, outdated, or not reviewed yet
                    if not latest_update or outdated or reviewed is not True:
                        flagged_objects.append(
                            {
                                "name": str(obj),
                                "type": label,
                                "latest_update": latest_update,
                                "reviewed": reviewed is True,
                                "id": obj.pk,
                                "url": obj.get_absolute_url(),
                            }
                        )

            # If *no* objects have the CF data populated at all, show info text
            missing_cf_data = valid_objects == 0

        except Exception as e:
            logger.exception(f"Error building flagged list: {e}")

        message = ""
        if missing_cf_data:
            # Note: the actual custom field names are latest_update / reviewed.
            # When filtering, you'll use cf_latest_update / cf_reviewed.
            message = (
                "No documentation data found. "
                "The custom fields 'latest_update' (Date) and 'reviewed' (Boolean) "
                "have been ensured for Devices and Virtual Machines. "
                "Use 'Check Fields' or 'Update Fields' to initialize values."
            )

        context = {
            "flagged_objects": flagged_objects,
            "search_query": search_query,
            "message": message,
        }
        return render(request, self.template_name, context)