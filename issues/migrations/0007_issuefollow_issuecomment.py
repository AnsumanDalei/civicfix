from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0006_emailotp_hash_storage"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IssueComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.CharField(max_length=1000)),
                ("is_hidden", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="issues.issue")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issue_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="IssueFollow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followers", to="issues.issue")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followed_issues", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="issuefollow",
            constraint=models.UniqueConstraint(fields=("issue", "user"), name="unique_issue_follower"),
        ),
        migrations.AddIndex(
            model_name="issuefollow",
            index=models.Index(fields=["user", "created_at"], name="issfollow_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="issuecomment",
            index=models.Index(fields=["issue", "is_hidden", "created_at"], name="isscomment_issue_hidden_idx"),
        ),
    ]
