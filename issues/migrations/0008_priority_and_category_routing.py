from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("issues", "0007_issuefollow_issuecomment")]

    operations = [
        migrations.AddField(
            model_name="issue", name="priority",
            field=models.CharField(choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical")], default="normal", max_length=12),
        ),
        migrations.CreateModel(
            name="CategoryRouting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("hazard", "Public Hazard (live wire, gas leak, open manhole)"), ("sanitation", "Sanitation (garbage, drainage, sewage)"), ("infrastructure", "Infrastructure (pothole, streetlight, road damage)"), ("other", "Other")], max_length=20, unique=True)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="routing_rules", to="issues.department")),
            ],
            options={"verbose_name": "Category routing rule", "verbose_name_plural": "Category routing rules"},
        ),
    ]
