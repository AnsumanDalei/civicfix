import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, IssueHistory, Notification, UserSettings

logger = logging.getLogger("issues")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
        UserSettings.objects.get_or_create(user=instance)


# Events that are worth notifying the reporter about. "created" and "edited"
# are left out on purpose — the reporter just did those themselves.
NOTIFY_EVENTS = {"assigned", "resolved", "status_changed", "commented", "priority_changed"}


@receiver(post_save, sender=IssueHistory)
def notify_on_issue_update(sender, instance, created, **kwargs):
    """Fires for every IssueHistory entry (created whenever an issue's status,
    assignment, or resolution changes — see Issue.log_history and mark_resolved
    in models.py). Creates an in-app Notification and sends an email to the
    person who reported the issue. Both are best-effort: this must never break
    the staff action (resolve/assign/etc.) that triggered it, so every failure
    is caught and logged instead of raised.
    """
    if not created or instance.event not in NOTIFY_EVENTS:
        return

    try:
        issue = instance.issue
        event_label = instance.get_event_display()
        recipients = {issue.reported_by_id}
        if instance.event in {"status_changed", "resolved", "assigned", "commented", "priority_changed"}:
            recipients.update(issue.followers.values_list("user_id", flat=True))
        for user_id in recipients - ({instance.actor_id} if instance.actor_id else set()):
            if not user_id:
                continue
            preferences = UserSettings.objects.filter(user_id=user_id).only("in_app_notifications", "issue_updates").first()
            if preferences is None or (preferences.in_app_notifications and preferences.issue_updates):
                message = (f'Your report "{issue.title}" has a new update.' if instance.event == "status_changed"
                           else f'An update was posted on "{issue.title}".' if instance.event == "commented"
                           else f'Your followed issue "{issue.title}" had its priority changed.' if instance.event == "priority_changed"
                           else f'Your followed issue "{issue.title}" was {event_label.lower()}.')
                if instance.note and instance.event != "commented":
                    message += f" ({instance.note})"
                Notification.objects.get_or_create(user_id=user_id, issue=issue, message=message[:255], is_read=False)

        recipient = issue.reported_by
        if recipient is None or (instance.actor_id and instance.actor_id == recipient.id):
            return

        if recipient.email:
            preferences = UserSettings.objects.filter(user=recipient).only("email_notifications", "issue_updates").first()
            if preferences and (not preferences.email_notifications or not preferences.issue_updates):
                return
            try:
                site_url = getattr(settings, "SITE_URL", "").rstrip("/")
                issue_url = f"{site_url}/issues/{issue.pk}/" if site_url else ""
                body = (
                    f"Hi {recipient.username},\n\n"
                    f'There is an update on the issue you reported, "{issue.title}":\n\n'
                    f"{event_label}"
                    + (f" — {instance.note}" if instance.note else "")
                    + "\n\n"
                    + (f"View it here: {issue_url}\n\n" if issue_url else "")
                    + "— CivicFix"
                )
                send_mail(
                    subject=f'CivicFix — update on "{issue.title}"',
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    fail_silently=True,
                )
            except Exception:
                # Email is a nice-to-have here; never let it break the request.
                logger.exception("Failed to send issue-update email for issue #%s", issue.pk)
    except Exception:
        logger.exception("notify_on_issue_update failed for history entry #%s", instance.pk)
