import math
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .storage import PrivateSupportStorage


CATEGORY_CHOICES = [
    ("hazard", _("Public Hazard (live wire, gas leak, open manhole)")),
    ("sanitation", _("Sanitation (garbage, drainage, sewage)")),
    ("infrastructure", _("Infrastructure (pothole, streetlight, road damage)")),
    ("other", _("Other")),
]

STATUS_CHOICES = [
    ("open", _("Open")),
    ("in_progress", _("In Progress")),
    ("resolved", _("Resolved")),
]

PRIORITY_CHOICES = [("low", _("Low")), ("medium", _("Medium")), ("high", _("High"))]
def haversine_meters(lat1, lon1, lat2, lon2):
    """distance between two lat/lon points in meters"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


class Issue(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="medium")

    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issues"
    )
    upvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="upvoted_issues", blank=True
    )

    department = models.ForeignKey(
        "Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="issues"
    )

    photo = models.ImageField(upload_to="issue_photos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.category}] {self.title}"

    def save(self, *args, **kwargs):
        adding = self._state.adding
        if self.reported_by_id is None:
            raise ValidationError({"reported_by": "An issue must have a reporter."})

        resolved_at_changed = False
        if self.status == "resolved" and self.resolved_at is None:
            self.resolved_at = timezone.now()
            resolved_at_changed = True
        elif self.status != "resolved" and self.resolved_at is not None:
            self.resolved_at = None
            resolved_at_changed = True

        if resolved_at_changed and kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"resolved_at"}
        if adding and self.category == "hazard" and self.priority == "medium":
            self.priority = "high"
        super().save(*args, **kwargs)

    @property
    def upvote_count(self):
        return self.upvoted_by.count()

    def find_possible_duplicate(self):
        radius = settings.DUPLICATE_RADIUS_METERS
        lat_delta = radius / 111_000
        lon_delta = radius / (111_000 * max(abs(math.cos(math.radians(self.latitude))), 0.01))
        candidates = Issue.objects.filter(
            category=self.category,
            status__in=["open", "in_progress"],
            latitude__gte=self.latitude-lat_delta,
            latitude__lte=self.latitude+lat_delta,
            longitude__gte=self.longitude-lon_delta,
            longitude__lte=self.longitude+lon_delta,
        ).exclude(pk=self.pk)
        nearest = None
        nearest_distance = radius
        for other in candidates:
            dist = haversine_meters(self.latitude, self.longitude, other.latitude, other.longitude)
            if dist <= nearest_distance:
                nearest, nearest_distance = other, dist
        return nearest

    def mark_resolved(self, actor=None, note=""):
        if self.status == "resolved":
            return False
        self.status = "resolved"
        self.resolved_at = timezone.now()
        self.save()
        IssueHistory.objects.create(
            issue=self, event="resolved", actor=actor,
            note=note.strip()[:255] or "Marked resolved",
        )
        return True

    def update_status(self, status, actor, note):
        if status not in {"open", "in_progress"}:
            raise ValueError("Only open and in-progress are staff-selectable statuses.")
        if self.status == "resolved":
            raise ValueError("Reopen a resolved issue before changing its status.")
        if self.status == status:
            return False
        self.status = status
        self.save(update_fields=["status", "updated_at"])
        IssueHistory.objects.create(
            issue=self,
            event="status_changed",
            actor=actor,
            note=note.strip()[:255],
        )
        return True

    def update_priority(self, priority, actor, note):
        if priority not in dict(PRIORITY_CHOICES):
            raise ValueError("Choose a valid priority level.")
        if self.status == "resolved":
            raise ValueError("Reopen a resolved issue before changing its priority.")
        if self.priority == priority:
            return False
        self.priority = priority
        self.save(update_fields=["priority", "updated_at"])
        IssueHistory.objects.create(issue=self, event="priority_changed", actor=actor,
                                    note=(note.strip() or f"Priority set to {self.get_priority_display()}")[:255])
        return True

    def log_history(self, event, actor=None, note=""):
        IssueHistory.objects.create(issue=self, event=event, actor=actor, note=note)

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CategoryRouting(models.Model):
    """Admin-configured category-to-department routing rule."""
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="routing_rules")

    class Meta:
        verbose_name = "Category routing rule"
        verbose_name_plural = "Category routing rules"

    def __str__(self):
        return f"{self.get_category_display()} → {self.department}"


class IssuePhoto(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="issue_photos/gallery/")
    caption = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


HISTORY_EVENT_CHOICES = [
    ("created", "Reported"),
    ("edited", "Edited"),
    ("status_changed", "Status changed"),
    ("assigned", "Assigned to department"),
    ("resolved", "Resolved"),
    ("commented", "Community update"),
    ("priority_changed", "Priority changed"),
]


class IssueHistory(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="history")
    event = models.CharField(max_length=20, choices=HISTORY_EVENT_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Issue history entries"

    def __str__(self):
        return f"Issue #{self.issue_id}: {self.get_event_display()}"


class Notification(models.Model):
    """In-app notification, polled from the topbar bell. Created automatically
    whenever an IssueHistory entry is logged for one of the user's issues
    (see signals.py) — status changes, department assignment,
    and resolution."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    issue = models.ForeignKey(
        Issue, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.message}"


class IssueFollow(models.Model):
    """A resident's subscription to updates on a public issue."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="followers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_issues")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["issue", "user"], name="unique_issue_follower")]
        indexes = [models.Index(fields=["user", "created_at"], name="issfollow_user_created_idx")]


class IssueComment(models.Model):
    """Authenticated community updates; staff can hide inappropriate posts."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issue_comments")
    body = models.CharField(max_length=1000)
    is_hidden = models.BooleanField(default=False)
    is_helpful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["issue", "is_hidden", "created_at"], name="isscomment_issue_hidden_idx")]

    def __str__(self):
        return f"Update on issue #{self.issue_id} by {self.user}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True,unique=True,null=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


class UserSettings(models.Model):
    THEME_CHOICES = [("system", "System"), ("light", "Light"), ("dark", "Dark")]
    LANGUAGE_CHOICES = [("en", "English"), ("hi", "Hindi"), ("or", "Odia")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings_preferences")
    locality = models.CharField(max_length=120, blank=True)
    preferred_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="system")
    in_app_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    issue_updates = models.BooleanField(default=True)
    area_alerts = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.user.username}"


class WatchArea(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watch_areas")
    locality = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "locality", "category"], name="unique_user_watch_area")]
        ordering = ["locality", "category"]

    def __str__(self):
        return f"{self.locality} ({self.get_category_display() if self.category else 'all categories'})"


SUPPORT_CATEGORY_CHOICES = [
    ("account", "Account help"), ("technical", "Technical problem"),
    ("feedback", "Feedback or suggestion"), ("feature", "Feature request"),
    ("other", "Other"),
]
SUPPORT_STATUS_CHOICES = [("open", "Open"), ("in_progress", "In progress"), ("resolved", "Resolved")]
SUPPORT_PRIORITY_CHOICES = [("low", "Low"), ("normal", "Normal"), ("high", "High")]


def support_attachment_path(instance, filename):
    return f"support_tickets/{instance.requester_id}/{instance.reference or 'new'}/{filename}"


class SupportTicket(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
    reference = models.CharField(max_length=16, unique=True, editable=False)
    category = models.CharField(max_length=16, choices=SUPPORT_CATEGORY_CHOICES, default="other")
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=5000)
    attachment = models.ImageField(upload_to=support_attachment_path, storage=PrivateSupportStorage(), blank=True, null=True)
    status = models.CharField(max_length=16, choices=SUPPORT_STATUS_CHOICES, default="open")
    priority = models.CharField(max_length=12, choices=SUPPORT_PRIORITY_CHOICES, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            import uuid
            self.reference = f"CFH-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference}: {self.subject}"


class SupportReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_replies")
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AccountDeletionRequest(models.Model):
    STATUS_CHOICES = [("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deletion_requests")
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_deletion_requests")

    class Meta:
        ordering = ["-created_at"]



class ContactMessage(models.Model):
    """Persist public contact-form submissions even when email delivery fails."""
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.name} ({self.created_at:%Y-%m-%d})"
