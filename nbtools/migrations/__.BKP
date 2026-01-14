from django.db import migrations

def create_custom_fields(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    CustomField = apps.get_model("extras", "CustomField")
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
            "type": "date",
        }
    )
    cf_date.content_types.set([ct_device, ct_vm])

    # Create or get the Reviewed field
    cf_bool, _ = CustomField.objects.get_or_create(
        name="reviewed",
        defaults={
            "label": "Reviewed",
            "type": "boolean",
            "default": False
        }
    )
    cf_bool.content_types.set([ct_device, ct_vm])

class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0002_squashed_0059"),
        ("contenttypes", "0001_initial"),
        ("dcim", "0003_squashed_0130"),
        ("virtualization", "0001_squashed_0022"),
        ("nbtools", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_custom_fields, reverse_code=migrations.RunPython.noop),
    ]
