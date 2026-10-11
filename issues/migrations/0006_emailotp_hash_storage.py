from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0005_alter_profile_phone"),
    ]

    operations = [
        migrations.RunPython(
            lambda apps, schema_editor: apps.get_model("issues", "EmailOTP").objects.all().delete(),
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="emailotp",
            name="otp",
            field=models.CharField(max_length=128),
        ),
    ]
