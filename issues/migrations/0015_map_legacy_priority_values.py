from django.db import migrations


def simplify_priority_values(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    Issue.objects.filter(priority="normal").update(priority="medium")
    Issue.objects.filter(priority="critical").update(priority="high")


class Migration(migrations.Migration):
    dependencies = [("issues", "0014_remove_issue_duplicate_of_delete_emailotp")]

    operations = [migrations.RunPython(simplify_priority_values, migrations.RunPython.noop)]
