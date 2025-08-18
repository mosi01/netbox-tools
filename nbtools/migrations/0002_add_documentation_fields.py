from django.db import migrations
import datetime

def create_and_backfill_fields(apps, schema_editor):
    # Get models
    ContentType = apps.get_model("contenttypes", "ContentType")
    CustomField = apps.get_model("extras", "CustomField")
    CustomFieldValue = apps.get_model("extras", "CustomFieldValue")
    Device = apps.get_model("dcim", "Device")
    VirtualMachine = apps.get_model("virtualization", "VirtualMachine")

    # Identify content types
    ct_device = ContentType.objects.get_for_model(Device)
    ct_vm = ContentType.objects.get_for_model(VirtualMachine)

    # Create or get the Latest Update field
    cf_date, _ = CustomField.objects.get_or_create(
        name="latest_update",
        defaults={
            "label": "Latest Update",
            "type": "date",  # Use raw string if TYPE_DATE isn't available
        }
    )
    cf_date.content_types.set([ct_device, ct_vm])

    # Create or get the Reviewed field
    cf_bool, _ = CustomField.objects.get_or_create(
        name="reviewed",
        defaults={
            "label": "Reviewed",
            "type": "boolean",  # Use raw string if TYPE_BOOLEAN isn't available
            "default": "false"
        }
    )
    cf_bool.content_types.set([ct_device, ct_vm])

    # Backfill values
    cutoff_date = datetime.date(2025, 1, 1)
    for model, ct in ((Device, ct_device), (VirtualMachine, ct_vm)):
        for obj in model.objects.all():
            obj_date = getattr(obj, "created", cutoff_date)
            effective_date = max(obj_date.date(), cutoff_date)

            CustomFieldValue.objects.update_or_create(
                field=cf_date,
                assigned_object_type=ct,
                assigned_object_id=obj.pk,
                defaults={"value": str(effective_date)}
            )

            CustomFieldValue.objects.update_or_create(
                field=cf_bool,
                assigned_object_type=ct,
                assigned_object_id=obj.pk,
                defaults={"value": "false"}
            )

class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0002_squashed_0059"),
        ("contenttypes", "0001_initial"),
        ("dcim", "0003_squashed_0130"),
        ("virtualization", "0001_squashed_0022"),
        ("nbtools", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_and_backfill_fields, reverse_code=migrations.RunPython.noop),
    ]
