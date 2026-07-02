"""
Unit tests for CivicFix core logic. Run with: python manage.py test
Also wired into CI (see .github/workflows/ci.yml).
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Issue, haversine_meters


class HaversineTests(TestCase):
    def test_same_point_is_zero_distance(self):
        self.assertAlmostEqual(haversine_meters(12.9, 77.6, 12.9, 77.6), 0, delta=0.01)

    def test_known_distance_two_points(self):
        # Two points roughly 1.1km apart (arbitrary coordinates, just testing the math)
        d = haversine_meters(12.9352, 77.6146, 12.9279, 77.6271)
        self.assertTrue(1000 < d < 2000)


class IssuePriorityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="testpass123")

    def _make_issue(self, **kwargs):
        defaults = dict(
            title="Pothole on Main Street",
            description="Large pothole causing traffic",
            category="infrastructure",
            latitude=12.9716,
            longitude=77.5946,
            reported_by=self.user,
        )
        defaults.update(kwargs)
        return Issue.objects.create(**defaults)

    def test_sla_deadline_set_automatically(self):
        issue = self._make_issue()
        self.assertIsNotNone(issue.sla_deadline)
        self.assertTrue(issue.sla_deadline > timezone.now())

    def test_hazard_has_higher_priority_than_other(self):
        hazard = self._make_issue(category="hazard", title="Open manhole")
        other = self._make_issue(category="other", title="Faded signboard")
        self.assertGreater(hazard.priority_score, other.priority_score)

    def test_upvotes_increase_priority_score(self):
        issue = self._make_issue()
        before = issue.priority_score
        bob = User.objects.create_user("bob", password="testpass123")
        issue.upvoted_by.add(bob)
        self.assertGreater(issue.priority_score, before)

    def test_resolved_issue_has_zero_priority(self):
        issue = self._make_issue()
        issue.mark_resolved()
        self.assertEqual(issue.priority_score, 0)


class DuplicateDetectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carol", password="testpass123")

    def test_nearby_same_category_flagged_as_duplicate(self):
        original = Issue.objects.create(
            title="Garbage pileup", description="Smells bad", category="sanitation",
            latitude=12.9716, longitude=77.5946, reported_by=self.user,
        )
        nearby = Issue(
            title="Trash heap", description="Same spot basically", category="sanitation",
            latitude=12.97165, longitude=77.59465, reported_by=self.user,
        )
        nearby.save()
        dup = nearby.find_possible_duplicate()
        self.assertEqual(dup.pk, original.pk)

    def test_far_away_same_category_not_flagged(self):
        Issue.objects.create(
            title="Garbage pileup", description="Smells bad", category="sanitation",
            latitude=12.9716, longitude=77.5946, reported_by=self.user,
        )
        far = Issue(
            title="Different garbage issue", description="Far away", category="sanitation",
            latitude=13.05, longitude=77.70, reported_by=self.user,
        )
        far.save()
        self.assertIsNone(far.find_possible_duplicate())


class EscalationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dave", password="testpass123")

    def test_escalate_bumps_tier(self):
        issue = Issue.objects.create(
            title="Streetlight out", description="Dark street", category="infrastructure",
            latitude=12.9, longitude=77.6, reported_by=self.user,
        )
        self.assertEqual(issue.escalation_tier, 1)
        issue.escalate()
        self.assertEqual(issue.escalation_tier, 2)
        self.assertEqual(issue.status, "escalated")
