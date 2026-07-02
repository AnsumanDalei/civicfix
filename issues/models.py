import math
from django.conf import settings
from django.db import models
from django.utils import timezone


CATEGORY_CHOICES = [
    ("hazard", "Public Hazard (live wire, gas leak, open manhole)"),
    ("sanitation", "Sanitation (garbage, drainage, sewage)"),
    ("infrastructure", "Infrastructure (pothole, streetlight, road damage)"),
    ("other", "Other"),
]

STATUS_CHOICES = [
    ("open", "Open"),
    ("in_progress", "In Progress"),
    ("escalated", "Escalated"),
    ("resolved", "Resolved"),
]

TIER_CHOICES = [
    (1, settings.ESCALATION_TIER_NAMES[1]),
    (2, settings.ESCALATION_TIER_NAMES[2]),
    (3, settings.ESCALATION_TIER_NAMES[3]),
]

# Base severity weight per category, used in the priority score formula.
SEVERITY_WEIGHT = {
    "hazard": 50,
    "sanitation": 20,
    "infrastructure": 15,
    "other": 5,
}


def haversine_meters(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in meters."""
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

    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issues"
    )
    upvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="upvoted_issues", blank=True
    )

    escalation_tier = models.PositiveSmallIntegerField(choices=TIER_CHOICES, default=1)
    sla_deadline = models.DateTimeField()
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates"
    )

    photo = models.ImageField(upload_to="issue_photos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.category}] {self.title}"

    # ---- business logic -------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.sla_deadline:
            hours = settings.SLA_HOURS_BY_CATEGORY.get(self.category, 168)
            self.sla_deadline = timezone.now() + timezone.timedelta(hours=hours)
        super().save(*args, **kwargs)

    @property
    def upvote_count(self):
        return self.upvoted_by.count()

    @property
    def age_hours(self):
        return (timezone.now() - self.created_at).total_seconds() / 3600

    @property
    def is_overdue(self):
        return self.status not in ("resolved",) and timezone.now() > self.sla_deadline

    @property
    def priority_score(self):
        """
        Higher = more urgent.
        score = severity_weight + (2 * upvotes) + age_bonus - resolved_penalty
        age_bonus grows the longer an issue sits open, so stale issues
        naturally float to the top even without new upvotes.
        """
        if self.status == "resolved":
            return 0
        base = SEVERITY_WEIGHT.get(self.category, 5)
        upvote_bonus = self.upvote_count * 2
        age_bonus = min(self.age_hours / 4, 40)  # capped so age can't dominate forever
        overdue_bonus = 25 if self.is_overdue else 0
        return round(base + upvote_bonus + age_bonus + overdue_bonus, 1)

    def find_possible_duplicate(self):
        """Return an existing open Issue of the same category within the
        configured radius, or None."""
        candidates = Issue.objects.filter(
            category=self.category,
            status__in=["open", "in_progress", "escalated"],
        ).exclude(pk=self.pk)
        for other in candidates:
            dist = haversine_meters(self.latitude, self.longitude, other.latitude, other.longitude)
            if dist <= settings.DUPLICATE_RADIUS_METERS:
                return other
        return None

    def escalate(self):
        """Bump to the next tier and extend the SLA deadline. Called by the
        escalate_issues management command once the SLA has been missed."""
        if self.escalation_tier < 3:
            self.escalation_tier += 1
        self.status = "escalated"
        extra_hours = settings.SLA_HOURS_BY_CATEGORY.get(self.category, 168) / 2
        self.sla_deadline = timezone.now() + timezone.timedelta(hours=extra_hours)
        self.save()

    def mark_resolved(self):
        self.status = "resolved"
        self.resolved_at = timezone.now()
        self.save()


class EscalationLog(models.Model):
    """Audit trail: every automatic escalation is recorded here so the
    transparency dashboard can show a full history per issue."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="escalation_logs")
    from_tier = models.PositiveSmallIntegerField()
    to_tier = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=255, default="SLA deadline missed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Issue #{self.issue_id}: tier {self.from_tier} -> {self.to_tier}"
