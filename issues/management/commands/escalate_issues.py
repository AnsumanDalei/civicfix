from django.core.management.base import BaseCommand
from django.utils import timezone

from issues.models import Issue, EscalationLog


class Command(BaseCommand):
    """
    Scans all open/in_progress issues; any whose SLA deadline has passed
    gets bumped to the next escalation tier and logged.

    Intended to run on a schedule (cron, Celery beat, or a Jenkins/GitHub
    Actions scheduled job hitting this via `manage.py escalate_issues`):

        */30 * * * *  cd /app && python manage.py escalate_issues
    """
    help = "Escalate overdue civic issues to the next authority tier."

    def handle(self, *args, **options):
        overdue = Issue.objects.exclude(status__in=["resolved"]).filter(
            sla_deadline__lt=timezone.now()
        )
        count = 0
        for issue in overdue:
            old_tier = issue.escalation_tier
            issue.escalate()
            EscalationLog.objects.create(
                issue=issue,
                from_tier=old_tier,
                to_tier=issue.escalation_tier,
                reason="SLA deadline missed",
            )
            count += 1
            self.stdout.write(
                f"Escalated issue #{issue.id} '{issue.title}' "
                f"tier {old_tier} -> {issue.escalation_tier}"
            )

        self.stdout.write(self.style.SUCCESS(f"Done. {count} issue(s) escalated."))
