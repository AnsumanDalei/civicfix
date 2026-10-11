from django.db import migrations


def normalize_legacy_statuses(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    Issue.objects.filter(status="escalated").update(status="in_progress")


class Migration(migrations.Migration):
    dependencies = [("issues", "0016_remove_issue_confirmed_at_remove_issue_confirmed_by_and_more")]
    operations = [migrations.RunPython(normalize_legacy_statuses, migrations.RunPython.noop)]
