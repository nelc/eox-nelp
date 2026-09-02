"""Normalizes MT delivery rows whose response code was stored as the string "None"."""
from django.db import migrations


def null_out_none_strings(apps, schema_editor):
    """Replace the literal "None" with a real NULL.

    `_record_mt_delivery` used to store `str(response.get("responseCode"))`, so a
    partner response carrying no code was written as the four-character string
    "None" rather than left empty. That value is indistinguishable from a real code
    at a glance and is missed by `last_response_code__isnull=True`.
    """
    model = apps.get_model("eox_nelp", "MTTrainingStageDelivery")
    model.objects.filter(last_response_code="None").update(last_response_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ('eox_nelp', '0019_add_mt_training_stage_delivery'),
    ]

    operations = [
        migrations.RunPython(null_out_none_strings, migrations.RunPython.noop),
    ]
