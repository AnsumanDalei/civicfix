import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Issue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("hazard", "Public Hazard (live wire, gas leak, open manhole)"),
                            ("sanitation", "Sanitation (garbage, drainage, sewage)"),
                            ("infrastructure", "Infrastructure (pothole, streetlight, road damage)"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("in_progress", "In Progress"),
                            ("escalated", "Escalated"),
                            ("resolved", "Resolved"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("address", models.CharField(blank=True, max_length=255)),
                (
                    "escalation_tier",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "Local Authority"), (2, "Regional Authority"), (3, "Top Authority")],
                        default=1,
                    ),
                ),
                ("sla_deadline", models.DateTimeField()),
                ("photo", models.ImageField(blank=True, null=True, upload_to="issue_photos/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "duplicate_of",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="duplicates",
                        to="issues.issue",
                    ),
                ),
                (
                    "reported_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issues",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "upvoted_by",
                    models.ManyToManyField(
                        blank=True, related_name="upvoted_issues", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="EscalationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_tier", models.PositiveSmallIntegerField()),
                ("to_tier", models.PositiveSmallIntegerField()),
                ("reason", models.CharField(default="SLA deadline missed", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escalation_logs",
                        to="issues.issue",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
