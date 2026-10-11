import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .models import Issue, PRIORITY_CHOICES, haversine_meters


class IssueAdminCreationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="issue_admin", email="admin@example.test", password="AdminPass!2026"
        )
        self.selected_reporter = User.objects.create_user(
            username="selected_reporter", password="ReporterPass!2026"
        )
        self.client.force_login(self.admin_user)
        self.add_url = reverse("admin:issues_issue_add")

    def issue_form_data(self, **overrides):
        data = {
            "title": "Streetlight out",
            "description": "The streetlight is not working near the park.",
            "category": "infrastructure",
            "status": "open",
            "priority": "medium",
            "latitude": "20.2961",
            "longitude": "85.8245",
            "address": "Unit 4, Bhubaneswar",
            "reported_by": "",
            "department": "",
        }
        data.update(overrides)
        return data

    def test_admin_issue_defaults_reporter_and_saves_automatic_timestamps(self):
        form_page = self.client.get(self.add_url)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, "Choose a reporter, or leave blank to use your account.")
        self.assertFalse(form_page.context["adminform"].form.fields["reported_by"].required)

        before_save = timezone.now()
        response = self.client.post(self.add_url, self.issue_form_data())
        self.assertEqual(response.status_code, 302)
        issue = Issue.objects.get(title="Streetlight out")
        after_save = timezone.now()

        self.assertEqual(issue.reported_by, self.admin_user)
        self.assertIsNotNone(issue.created_at)
        self.assertIsNotNone(issue.updated_at)
        self.assertGreaterEqual(issue.created_at, before_save)
        self.assertLessEqual(issue.created_at, after_save)
        self.assertGreaterEqual(issue.updated_at, before_save)
        self.assertLessEqual(issue.updated_at, after_save)
        self.assertIsNone(issue.resolved_at)

    def test_admin_can_select_reporter_and_resolved_issue_gets_resolution_time(self):
        response = self.client.post(self.add_url, self.issue_form_data(
            title="Resolved pothole", status="resolved", reported_by=str(self.selected_reporter.pk),
        ))
        self.assertEqual(response.status_code, 302)
        issue = Issue.objects.get(title="Resolved pothole")
        self.assertEqual(issue.reported_by, self.selected_reporter)
        self.assertIsNotNone(issue.created_at)
        self.assertIsNotNone(issue.updated_at)
        self.assertIsNotNone(issue.resolved_at)


class HaversineTests(TestCase):
    def test_same_point_is_zero_distance(self):
        self.assertAlmostEqual(haversine_meters(12.9, 77.6, 12.9, 77.6), 0, delta=0.01)

    def test_known_distance_two_points(self):
        d = haversine_meters(12.9352, 77.6146, 12.9279, 77.6271)
        self.assertTrue(1000 < d < 2000)








class IssuePriorityTests(TestCase):
    def test_priority_has_three_easy_to_explain_levels(self):
        self.assertEqual([value for value, label in PRIORITY_CHOICES], ["low", "medium", "high"])


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



from .models import Profile, Department, IssueHistory, IssueFollow, IssueComment, CategoryRouting, Notification


class AuthenticationFlowTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_creates_account_then_requires_manual_login(self):
        from django.core import mail

        response = self.client.post(reverse("signup"), {
            "username": "new_citizen", "email": "citizen@example.test",
            "password1": "S3cureTestPass!2026", "password2": "S3cureTestPass!2026",
        })
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="new_citizen").exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        login_page = self.client.get(reverse("login"))
        self.assertContains(login_page, "Account created successfully. Please log in to continue.")
        self.assertEqual(mail.outbox[0].from_email, "CivicFix Team <civicfix.team@gmail.com>")
        login_response = self.client.post(reverse("login"), {
            "username": "new_citizen", "password": "S3cureTestPass!2026",
        })
        self.assertRedirects(login_response, reverse("landing"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_signup_succeeds_when_verification_email_cannot_be_delivered(self):
        with patch("issues.views.send_mail", side_effect=OSError("SMTP unavailable")):
            response = self.client.post(reverse("signup"), {
                "username": "mail_down_user", "email": "mail-down@example.test",
                "password1": "S3cureTestPass!2026", "password2": "S3cureTestPass!2026",
            })
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="mail_down_user").exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_logout_and_password_reset_pages(self):
        User.objects.create_user("login_citizen", password="S3cureTestPass!2026")
        response = self.client.post(reverse("login"), {"username": "login_citizen", "password": "S3cureTestPass!2026"})
        self.assertRedirects(response, reverse("landing"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("landing"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)

    def test_invalid_login_shows_an_authentication_error(self):
        User.objects.create_user("bad_login", password="CorrectPass!2026")
        response = self.client.post(reverse("login"), {"username": "bad_login", "password": "incorrect"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")

    def test_login_accepts_the_account_email(self):
        User.objects.create_user("email_login", email="email-login@example.test", password="CorrectPass!2026")
        response = self.client.post(reverse("login"), {"username": "EMAIL-LOGIN@example.test", "password": "CorrectPass!2026"})
        self.assertRedirects(response, reverse("landing"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_removed_dashboard_route_and_authenticated_home(self):
        citizen = User.objects.create_user("home_citizen", password="CorrectPass!2026")
        self.client.force_login(citizen)
        home = self.client.get(reverse("landing"))
        self.assertEqual(home.status_code, 200)
        self.assertNotContains(home, "My dashboard")
        self.assertEqual(self.client.get("/dashboard/").status_code, 404)
        profile = self.client.get(reverse("profile"))
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, "Your Reported Issues")

    def test_supported_and_followed_reports_remain_available_on_profile(self):
        citizen = User.objects.create_user("profile_community", password="CorrectPass!2026")
        issue = Issue.objects.create(title="Leaking water pipe", description="Water is leaking", category="infrastructure", latitude=20.3, longitude=85.8, reported_by=User.objects.create_user("pipe_reporter"))
        issue.upvoted_by.add(citizen)
        IssueFollow.objects.create(issue=issue, user=citizen)
        self.client.force_login(citizen)
        profile = self.client.get(reverse("profile"))
        self.assertContains(profile, "Issues you support")
        self.assertContains(profile, "Issues you follow")
        self.assertContains(profile, "Leaking water pipe")

    def test_staff_login_and_operations_page_remain_staff_only(self):
        staff = User.objects.create_user("ops_staff", password="CorrectPass!2026", is_staff=True)
        citizen = User.objects.create_user("ops_citizen", password="CorrectPass!2026")
        response = self.client.post(reverse("login"), {"username": staff.username, "password": "CorrectPass!2026"})
        self.assertRedirects(response, reverse("staff_operations"))
        self.assertEqual(self.client.get(reverse("staff_operations")).status_code, 200)
        self.client.force_login(citizen)
        self.assertEqual(self.client.get(reverse("staff_operations")).status_code, 302)


class ProfileAutoCreationTests(TestCase):
    def test_profile_created_automatically_for_new_user(self):
        user = User.objects.create_user("erin", password="testpass123")
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertFalse(user.profile.email_verified)


class IssueCrudViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("frank", password="testpass123")
        self.other = User.objects.create_user("grace", password="testpass123")
        self.issue = Issue.objects.create(
            title="Broken bench", description="Bench is cracked", category="other",
            latitude=12.9, longitude=77.6, reported_by=self.owner,
        )

    def test_owner_can_edit(self):
        self.client.login(username="frank", password="testpass123")
        url = reverse("issue_edit", args=[self.issue.pk])
        response = self.client.post(url, {
            "title": "Broken bench (fixed title)", "description": "Bench is badly cracked",
            "category": "other", "latitude": 12.9, "longitude": 77.6, "address": "",
        })
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "Broken bench (fixed title)")
        self.assertEqual(response.status_code, 302)

    def test_non_owner_cannot_edit(self):
        self.client.login(username="grace", password="testpass123")
        url = reverse("issue_edit", args=[self.issue.pk])
        self.client.post(url, {"title": "Hijacked title"})
        self.issue.refresh_from_db()
        self.assertNotEqual(self.issue.title, "Hijacked title")

    def test_owner_can_delete(self):
        self.client.login(username="frank", password="testpass123")
        url = reverse("issue_delete", args=[self.issue.pk])
        self.client.post(url)
        self.assertFalse(Issue.objects.filter(pk=self.issue.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.client.login(username="grace", password="testpass123")
        url = reverse("issue_delete", args=[self.issue.pk])
        self.client.post(url)
        self.assertTrue(Issue.objects.filter(pk=self.issue.pk).exists())

    def test_creating_issue_logs_history(self):
        self.client.login(username="frank", password="testpass123")
        response = self.client.post(reverse("report_issue"), {
            "title": "New crack in pavement", "description": "A deep crack near the crossing",
            "category": "infrastructure", "latitude": "13.15", "longitude": "77.95", "address": "North Road",
        })
        self.assertEqual(response.status_code, 302)
        created = Issue.objects.get(title="New crack in pavement")
        self.assertTrue(IssueHistory.objects.filter(issue=created, event="created").exists())


class SearchAndFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("henry", password="testpass123")
        Issue.objects.create(
            title="Water leak on Oak Street", description="Pipe burst", category="sanitation",
            latitude=12.9, longitude=77.6, reported_by=self.user,
        )
        Issue.objects.create(
            title="Pothole near the mall", description="Deep hole", category="infrastructure",
            latitude=12.9, longitude=77.6, reported_by=self.user,
        )
        self.client.login(username="henry", password="testpass123")

    def test_search_by_title(self):
        response = self.client.get(reverse("issue_list"), {"q": "Oak Street"})
        titles = [i.title for i in response.context["page_obj"]]
        self.assertIn("Water leak on Oak Street", titles)
        self.assertNotIn("Pothole near the mall", titles)

    def test_filter_by_category(self):
        response = self.client.get(reverse("issue_list"), {"category": "infrastructure"})
        titles = [i.title for i in response.context["page_obj"]]
        self.assertIn("Pothole near the mall", titles)
        self.assertNotIn("Water leak on Oak Street", titles)

    def test_unassigned_filter_matches_staff_queue(self):
        response = self.client.get(reverse("issue_list"), {"department": "unassigned"})
        titles = [i.title for i in response.context["page_obj"]]
        self.assertEqual(set(titles), {"Water leak on Oak Street", "Pothole near the mall"})

    def test_pagination_returns_page_obj(self):
        response = self.client.get(reverse("issue_list"))
        self.assertIn("page_obj", response.context)


class DepartmentAssignmentTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("ivy", password="testpass123", is_staff=True)
        self.user = User.objects.create_user("jack", password="testpass123")
        self.dept = Department.objects.create(name="Roads & Infrastructure")
        self.issue = Issue.objects.create(
            title="Cracked sidewalk", description="Trip hazard", category="infrastructure",
            latitude=12.9, longitude=77.6, reported_by=self.user,
        )

    def test_staff_can_assign_department(self):
        self.client.login(username="ivy", password="testpass123")
        url = reverse("assign_department", args=[self.issue.pk])
        self.client.post(url, {"department": self.dept.pk})
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.department, self.dept)

    def test_non_staff_cannot_access_assign_view(self):
        self.client.login(username="jack", password="testpass123")
        url = reverse("assign_department", args=[self.issue.pk])
        response = self.client.post(url, {"department": self.dept.pk})
        self.assertNotEqual(response.status_code, 200)
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.department)


class StaticPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("kim", password="testpass123")
        self.client.login(username="kim", password="testpass123")

    def test_about_page_loads(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_contact_page_sends_email_to_civicfix_team(self):
        from django.core import mail

        response = self.client.get(reverse("contact"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("contact"), {
            "name": "Kim", "email": "kim@example.com",
            "subject": "Question", "message": "How do I report an issue?",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["civicfix.team@gmail.com"])
        self.assertEqual(message.from_email, "CivicFix Team <civicfix.team@gmail.com>")
        self.assertIn("Kim", message.body)
        self.assertIn("kim@example.com", message.body)
        self.assertIn("How do I report an issue?", message.body)
        self.assertIn("Submitted:", message.body)
        self.assertContains(response, "Thanks — your message has been sent.")

    def test_contact_email_failure_shows_friendly_message(self):
        with patch("issues.views.send_mail", side_effect=OSError("SMTP unavailable")):
            response = self.client.post(reverse("contact"), {
                "name": "Kim", "email": "kim@example.com",
                "subject": "Question", "message": "How do I report an issue?",
            }, follow=True)
        self.assertContains(response, "Something went wrong sending your message. Please try again later.")
        self.assertNotContains(response, "SMTP unavailable")

    def test_auth_password_visibility_controls_are_eye_icons_inside_fields(self):
        login_page = self.client.get(reverse("login"))
        signup_page = self.client.get(reverse("signup"))
        self.assertContains(login_page, 'class="password-visibility-toggle"')
        self.assertContains(login_page, "data-eye-open")
        self.assertContains(signup_page, 'class="password-visibility-toggle"', count=2)
        self.assertContains(signup_page, "data-eye-closed", count=3)

    def test_profile_page_loads(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)


class CivicWorkflowTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user("reporter", password="testpass123")
        self.neighbour = User.objects.create_user("neighbour", password="testpass123")
        self.officer = User.objects.create_user("officer", password="testpass123", is_staff=True)
        self.issue = Issue.objects.create(
            title="Broken streetlight", description="Dark at the crossing", category="infrastructure",
            latitude=12.9, longitude=77.6, reported_by=self.reporter,
        )

    def test_issue_discovery_is_available_before_signup(self):
        self.assertEqual(self.client.get(reverse("issue_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("issue_detail", args=[self.issue.pk])).status_code, 200)


    def test_reporter_can_reopen_resolved_issue_with_reason(self):
        self.issue.mark_resolved(actor=self.officer, note="Crew attended")
        self.client.force_login(self.reporter)
        response = self.client.post(reverse("reopen_issue", args=[self.issue.pk]), {"reason": "Light is still out"})
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "open")
        self.assertIsNone(self.issue.resolved_at)
        self.assertTrue(self.issue.history.filter(event="status_changed", note__contains="Light is still out").exists())

    def test_another_resident_cannot_reopen_issue(self):
        self.issue.mark_resolved(actor=self.officer)
        self.client.force_login(self.neighbour)
        self.client.post(reverse("reopen_issue", args=[self.issue.pk]))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "resolved")


    def test_resolved_issue_records_officer_note_once(self):
        self.client.force_login(self.officer)
        url = reverse("mark_resolved", args=[self.issue.pk])
        self.client.post(url, {"resolution_note": "Replaced the lamp"})
        self.client.post(url, {"resolution_note": "Duplicate submission"})
        entries = IssueHistory.objects.filter(issue=self.issue, event="resolved")
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.get().note, "Replaced the lamp")

    def test_staff_must_explain_resolution(self):
        self.client.force_login(self.officer)
        self.client.post(reverse("mark_resolved", args=[self.issue.pk]), {"resolution_note": "  "})
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "open")

    def test_staff_can_move_case_to_progress_with_a_history_note(self):
        self.client.force_login(self.officer)
        self.client.post(reverse("update_issue_status", args=[self.issue.pk]), {
            "status": "in_progress", "status_note": "Crew scheduled for tomorrow",
        })
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "in_progress")
        self.assertTrue(self.issue.history.filter(event="status_changed", note="Crew scheduled for tomorrow").exists())

    def test_resident_cannot_change_case_status(self):
        self.client.force_login(self.reporter)
        response = self.client.post(reverse("update_issue_status", args=[self.issue.pk]), {
            "status": "in_progress", "status_note": "Please update",
        })
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "open")


    def test_phone_number_remains_optional_on_profile(self):
        from .forms import ProfileForm
        form = ProfileForm(
            {"full_name": "Reporter", "email": "reporter@example.org", "phone": ""},
            instance=self.reporter.profile,
            user=self.reporter,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_report_form_rejects_missing_map_pin(self):
        from .forms import IssueForm
        form = IssueForm({
            "title": "New pothole", "description": "In the cycle lane", "category": "infrastructure",
            "latitude": "", "longitude": "", "address": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("Choose a valid location", str(form.non_field_errors()))

class CommunityFeatureTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user("follow_reporter", password="testpass123")
        self.neighbor = User.objects.create_user("follow_neighbor", password="testpass123")
        self.staff = User.objects.create_user("follow_staff", password="testpass123", is_staff=True)
        self.issue = Issue.objects.create(
            title="Streetlight not working", description="Dark crossing", category="infrastructure",
            latitude=12.9, longitude=77.6, reported_by=self.reporter,
        )

    def test_follow_toggle_is_authenticated_and_persists(self):
        url = reverse("follow_issue", args=[self.issue.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(IssueFollow.objects.exists())
        self.client.login(username="follow_neighbor", password="testpass123")
        self.client.post(url)
        self.assertTrue(IssueFollow.objects.filter(issue=self.issue, user=self.neighbor).exists())
        self.client.post(url)
        self.assertFalse(IssueFollow.objects.filter(issue=self.issue, user=self.neighbor).exists())

    def test_community_update_is_persisted_and_notifies_followers(self):
        IssueFollow.objects.create(issue=self.issue, user=self.neighbor)
        self.client.login(username="follow_reporter", password="testpass123")
        response = self.client.post(reverse("add_issue_comment", args=[self.issue.pk]), {"body": "The light is still out tonight."})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(IssueComment.objects.filter(issue=self.issue, body="The light is still out tonight.").exists())
        self.assertTrue(Notification.objects.filter(user=self.neighbor, issue=self.issue).exists())

    def test_comment_is_html_escaped_and_staff_can_hide(self):
        self.client.login(username="follow_neighbor", password="testpass123")
        self.client.post(reverse("add_issue_comment", args=[self.issue.pk]), {"body": "<script>alert(1)</script>"})
        comment = IssueComment.objects.get(issue=self.issue)
        response = self.client.get(reverse("issue_detail", args=[self.issue.pk]))
        self.assertContains(response, "&lt;script&gt;", html=False)
        self.client.login(username="follow_staff", password="testpass123")
        self.client.post(reverse("hide_issue_comment", args=[self.issue.pk, comment.pk]))
        comment.refresh_from_db()
        self.assertTrue(comment.is_hidden)

    def test_public_map_and_landing_show_database_reports(self):
        for name in ("issue_map", "landing", "analytics"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("issue_map")).context["map_points"][0]["id"], self.issue.pk)

    def test_report_stepper_and_authority_priority_control_render(self):
        self.client.login(username="follow_neighbor", password="testpass123")
        response = self.client.get(reverse("report_issue"))
        self.assertContains(response, "Step")
        self.client.login(username="follow_staff", password="testpass123")
        response = self.client.get(reverse("issue_detail", args=[self.issue.pk]))
        self.assertContains(response, "Update priority")

    def test_category_routing_assigns_department_on_new_report(self):
        department = Department.objects.create(name="Road response")
        CategoryRouting.objects.create(category="infrastructure", department=department)
        user = User.objects.create_user("route_user", password="testpass123")
        self.client.login(username="route_user", password="testpass123")
        response = self.client.post(reverse("report_issue"), {
            "title": "Sidewalk cracked", "description": "Cracked beside the bus stop", "category": "infrastructure",
            "latitude": "12.85", "longitude": "77.65", "address": "Market Road",
        })
        self.assertEqual(response.status_code, 302)
        routed = Issue.objects.get(title="Sidewalk cracked")
        self.assertEqual(routed.department, department)
        self.assertTrue(routed.history.filter(event="assigned").exists())

    def test_duplicate_prompt_offers_support_or_continue(self):
        self.client.login(username="follow_neighbor", password="testpass123")
        payload = {"title": "Streetlight out at crossing", "description": "The lamp is dark", "category": "infrastructure", "latitude": "12.9", "longitude": "77.6", "address": "Main crossing"}
        response = self.client.post(reverse("report_issue"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A similar issue may already be reported")
        self.assertEqual(Issue.objects.count(), 1)
        payload["allow_duplicate"] = "1"
        response = self.client.post(reverse("report_issue"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Issue.objects.count(), 2)



    def test_notification_center_is_private_paginated_and_can_mark_read(self):
        note = Notification.objects.create(user=self.neighbor, issue=self.issue, message="A report changed")
        self.assertEqual(self.client.get(reverse("notification_center")).status_code, 302)
        self.client.force_login(self.neighbor)
        page = self.client.get(reverse("notification_center"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "A report changed")
        response = self.client.post(reverse("notification_mark_read", args=[note.pk]))
        self.assertRedirects(response, reverse("issue_detail", args=[self.issue.pk]))
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_notification_cannot_be_marked_read_by_another_user(self):
        note = Notification.objects.create(user=self.neighbor, issue=self.issue, message="Private")
        self.client.force_login(self.reporter)
        response = self.client.post(reverse("notification_mark_read", args=[note.pk]))
        self.assertEqual(response.status_code, 404)
        note.refresh_from_db()
        self.assertFalse(note.is_read)

class BasicIssueApiTests(TestCase):
    def test_public_list_and_detail(self):
        from rest_framework.test import APIClient
        issue = Issue.objects.create(title="API pothole", description="Road surface damaged", category="infrastructure", latitude=20.3, longitude=85.8, reported_by=User.objects.create_user(username="api_reader"))
        client = APIClient()
        self.assertEqual(client.get("/api/issues/").status_code, 200)
        self.assertEqual(client.get(f"/api/issues/{issue.pk}/").status_code, 200)

    def test_authenticated_user_can_create_issue(self):
        from rest_framework.test import APIClient
        user = User.objects.create_user(username="api_creator", password="SafePass123!")
        client = APIClient(); client.force_authenticate(user=user)
        response = client.post("/api/issues/", {"title":"API drain", "description":"Drain is blocked", "category":"sanitation", "priority":"medium", "latitude":20.3, "longitude":85.8, "address":"Main Street"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Issue.objects.get(pk=response.data["id"]).reported_by, user)
    def test_staff_can_update_status_through_api(self):
        from rest_framework.test import APIClient
        staff = User.objects.create_user("api_staff", password="SafePass123!", is_staff=True)
        reporter = User.objects.create_user("api_reporter")
        issue = Issue.objects.create(title="API status", description="Test update", category="other", latitude=20.3, longitude=85.8, reported_by=reporter)
        client = APIClient(); client.force_authenticate(user=staff)
        response = client.patch(f"/api/issues/{issue.pk}/", {"status": "in_progress"}, format="json")
        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, "in_progress")



class FinalGapFeatureTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("gap_owner", password="testpass123")
        self.neighbor = User.objects.create_user("gap_neighbor", password="testpass123")
        self.staff = User.objects.create_user("gap_staff", password="testpass123", is_staff=True)

    def issue(self, **kwargs):
        fields = dict(title="Streetlight failed", description="Light is off at the crossing", category="infrastructure", latitude=20.30, longitude=85.82, reported_by=self.owner)
        fields.update(kwargs)
        return Issue.objects.create(**fields)





    def test_multi_photo_report_saves_primary_and_additional_gallery_image(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import IssuePhoto
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), "red").save(image_bytes, format="PNG")
        payload = {"title": "Road lamp failure", "description": "The light is out beside the footpath.", "category": "infrastructure", "latitude": "38.8", "longitude": "-77.1", "address": "Park entrance"}
        payload["photos"] = [SimpleUploadedFile("one.png", image_bytes.getvalue(), "image/png"), SimpleUploadedFile("two.png", image_bytes.getvalue(), "image/png")]
        self.client.force_login(self.owner)
        response = self.client.post(reverse("report_issue"), payload)
        self.assertEqual(response.status_code, 302)
        issue = Issue.objects.get(title=payload["title"])
        self.assertTrue(issue.photo)
        self.assertEqual(IssuePhoto.objects.filter(issue=issue).count(), 1)
        self.assertContains(self.client.get(reverse("issue_detail", args=[issue.pk])), "Additional photo", html=False)

    def test_map_filters_and_plain_markers_are_rendered(self):
        issue = self.issue(priority="high")
        response = self.client.get(reverse("issue_map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "map-priority")
        self.assertEqual(response.context["map_points"][0]["priority"], "high")
        self.assertContains(response, "L.circleMarker")


    def test_global_search_includes_issue_id_category_and_department(self):
        from .models import Department
        department = Department.objects.create(name="Night Lighting Team")
        issue = self.issue()
        issue.department = department
        issue.save(update_fields=["department"])
        for query in (f"CF-{issue.pk:06d}", "infrastructure", "Night Lighting Team"):
            response = self.client.get(reverse("issue_list"), {"q": query})
            self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_geocoding_is_authenticated_cached_and_returns_attributed_results(self):
        from unittest.mock import Mock, patch
        from django.core.cache import cache
        from django.test import override_settings
        import json
        cache.clear()
        result = [{"lat": "20.3", "lon": "85.82", "display_name": "Central Road, Bhubaneswar"}]
        response_obj = Mock()
        response_obj.__enter__ = Mock(return_value=response_obj)
        response_obj.__exit__ = Mock(return_value=False)
        response_obj.read.return_value = json.dumps(result).encode()
        self.client.force_login(self.neighbor)
        with override_settings(GEOCODING_BASE_URL="https://geo.example", GEOCODING_USER_AGENT="CivicFix/test"):
            with patch("issues.views.urlopen", return_value=response_obj) as opener:
                response = self.client.get(reverse("geocode"), {"q": "Central Road"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["results"][0]["display_name"], result[0]["display_name"])
            self.assertIn("OpenStreetMap", response.json()["attribution"])
            self.assertIn("CivicFix/test", opener.call_args.args[0].get_header("User-agent"))
            with patch("issues.views.urlopen", side_effect=AssertionError("cache should satisfy repeat")):
                self.assertEqual(self.client.get(reverse("geocode"), {"q": "Central Road"}).status_code, 200)

    def test_geocoding_failure_has_manual_pin_fallback(self):
        from unittest.mock import patch
        self.client.force_login(self.neighbor)
        with patch("issues.views.urlopen", side_effect=TimeoutError):
            response = self.client.get(reverse("geocode"), {"q": "Some address"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("manually", response.json()["error"])




    def test_staff_can_mark_a_community_update_helpful(self):
        from .models import IssueComment
        issue = self.issue()
        comment = IssueComment.objects.create(issue=issue, user=self.neighbor, body="The drain is still blocked.")
        url = reverse("mark_comment_helpful", args=[issue.pk, comment.pk])
        self.client.force_login(self.neighbor)
        self.assertEqual(self.client.post(url).status_code, 302)
        comment.refresh_from_db()
        self.assertFalse(comment.is_helpful)
        self.client.force_login(self.staff)
        self.client.post(url)
        comment.refresh_from_db()
        self.assertTrue(comment.is_helpful)


class SettingsModuleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("settings_owner", password="CorrectPass!2026")
        self.other = User.objects.create_user("settings_other", password="CorrectPass!2026")
        self.staff = User.objects.create_user("settings_staff", password="CorrectPass!2026", is_staff=True)

    def test_settings_requires_login_and_persists_theme_language_and_notifications(self):
        from .models import UserSettings
        url = reverse("user_settings")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watch areas")
        response = self.client.post(url, {
            "locality": "Unit 4", "preferred_category": "sanitation", "timezone": "Asia/Kolkata",
            "language": "hi", "theme": "dark", "in_app_notifications": "on",
            "email_notifications": "on", "issue_updates": "on", "area_alerts": "on",
        })
        self.assertRedirects(response, url)
        prefs = UserSettings.objects.get(user=self.owner)
        self.assertEqual((prefs.language, prefs.theme, prefs.locality), ("hi", "dark", "Unit 4"))
        self.assertEqual(response.cookies["django_language"].value, "hi")
        report_form = self.client.get(reverse("report_issue"))
        self.assertEqual(report_form.context["form"]["category"].value(), "sanitation")

    def test_invalid_preferences_do_not_persist(self):
        from .models import UserSettings
        self.client.force_login(self.owner)
        self.client.post(reverse("user_settings"), {"language": "xx", "theme": "rainbow", "timezone": "Mars"})
        prefs = UserSettings.objects.get(user=self.owner)
        self.assertEqual((prefs.language, prefs.theme, prefs.timezone), ("en", "system", "Asia/Kolkata"))

    def test_watch_area_is_private_removable_and_alerts_match_address_and_category(self):
        from .models import WatchArea, UserSettings, Notification
        self.client.force_login(self.owner)
        self.client.post(reverse("watch_area_add"), {"locality": "Unit 4", "category": "sanitation"})
        watch = WatchArea.objects.get(user=self.owner)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("watch_area_remove", args=[watch.pk])).status_code, 404)
        response = self.client.post(reverse("report_issue"), {
            "title": "Drain blocked", "description": "Wastewater", "category": "sanitation",
            "latitude": "20.3", "longitude": "85.8", "address": "Unit 4, Bhubaneswar",
        })
        self.assertEqual(response.status_code, 302)
        issue = Issue.objects.get(title="Drain blocked")
        self.assertTrue(Notification.objects.filter(user=self.owner, issue=issue, message__contains="Unit 4").exists())
        self.client.force_login(self.owner)
        self.client.post(reverse("watch_area_remove", args=[watch.pk]))
        self.assertFalse(WatchArea.objects.filter(pk=watch.pk).exists())

    def test_disabled_issue_notifications_are_respected(self):
        from .models import UserSettings, Notification
        from django.core import mail
        UserSettings.objects.update_or_create(user=self.owner, defaults={
            "in_app_notifications": False, "email_notifications": False, "issue_updates": False,
        })
        issue = Issue.objects.create(title="Drain", description="Blocked", category="sanitation", latitude=20.3, longitude=85.8, reported_by=self.owner)
        issue.log_history("status_changed", actor=self.staff, note="Crew assigned")
        self.assertFalse(Notification.objects.filter(user=self.owner, issue=issue).exists())
        self.assertFalse(mail.outbox)

    def test_user_can_export_only_their_nonsecret_data(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("user_data_export"))
        self.assertEqual(response["Content-Type"], "application/json")
        payload = json.loads(response.content)
        self.assertEqual(payload["profile"]["username"], self.owner.username)
        self.assertNotIn("password", response.content.decode().lower())
        self.assertNotIn("session", response.content.decode().lower())

    def test_account_deletion_requires_password_and_creates_review_request(self):
        from .models import AccountDeletionRequest
        self.client.force_login(self.owner)
        url = reverse("account_deletion_request")
        self.client.post(url, {"confirm_deletion": "yes", "password": "wrong"})
        self.assertFalse(AccountDeletionRequest.objects.exists())
        self.client.post(url, {"confirm_deletion": "yes", "password": "CorrectPass!2026"})
        request = AccountDeletionRequest.objects.get(user=self.owner)
        self.assertEqual(request.status, "pending")
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())

    def test_support_ticket_access_upload_listing_and_admin_authorization(self):
        from .models import SupportTicket, SupportReply
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from io import BytesIO
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), "white").save(image_buffer, format="PNG")
        screenshot = SimpleUploadedFile("screen.png", image_buffer.getvalue(), content_type="image/png")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("support_ticket_create"), {
            "category": "technical", "subject": "Map not loading", "message": "The issue map stays blank.",
            "attachment": screenshot,
        })
        ticket = SupportTicket.objects.get(requester=self.owner)
        self.assertRedirects(response, reverse("support_ticket_detail", args=[ticket.pk]))
        self.assertTrue(ticket.reference.startswith("CFH-"))
        self.assertTrue(ticket.attachment.name.startswith("support_tickets/"))
        with self.assertRaises(ValueError):
            ticket.attachment.url
        self.assertEqual(self.client.get(reverse("support_attachment", args=[ticket.pk])).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("support_ticket_detail", args=[ticket.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("support_attachment", args=[ticket.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("support_admin")).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("support_admin")).status_code, 200)
        self.client.post(reverse("support_ticket_detail", args=[ticket.pk]), {"message": "We are looking into it."})
        self.assertTrue(SupportReply.objects.filter(ticket=ticket, author=self.staff).exists())
        self.client.post(reverse("support_admin"), {"ticket_id": ticket.pk, "status": "in_progress", "priority": "high"})
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.priority), ("in_progress", "high"))

    def test_staff_reviews_account_deletion_without_auto_deleting_account(self):
        from .models import AccountDeletionRequest
        deletion = AccountDeletionRequest.objects.create(user=self.owner)
        self.client.force_login(self.staff)
        self.client.post(reverse("review_deletion_request", args=[deletion.pk]), {"decision": "approved"})
        deletion.refresh_from_db()
        self.assertEqual(deletion.status, "approved")
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())


class AIAssistantEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ai_citizen", password="CorrectPass!2026")
        self.client.force_login(self.user)
        self.url = reverse("ai_assist")

    def test_report_form_shows_optional_ai_controls(self):
        response = self.client.get(reverse("report_issue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Assist")
        self.assertContains(response, reverse("ai_assist"))

    def test_missing_key_returns_friendly_message_and_does_not_block_reporting(self):
        from django.test import override_settings
        with override_settings(OPENAI_API_KEY=""):
            response = self.client.post(self.url, data='{"action":"improve","description":"lamp is broken"}', content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("continue entering the report manually", response.json()["error"])

    def test_description_is_sent_to_provider_and_suggestion_is_returned(self):
        from unittest.mock import Mock, patch
        from django.test import override_settings
        import json
        api_response = Mock()
        api_response.__enter__ = Mock(return_value=api_response)
        api_response.__exit__ = Mock(return_value=False)
        api_response.read.return_value = json.dumps({"output": [{"content": [{"type": "output_text", "text": "A streetlight is not working near the crossing."}]}]}).encode()
        with override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-5-mini"):
            with patch("issues.ai_assistant.urlopen", return_value=api_response) as opener:
                response = self.client.post(self.url, data=json.dumps({"action":"improve", "description":"lamp broken near crossing"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not working near the crossing", response.json()["result"])
        request = opener.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["input"], "lamp broken near crossing")
        self.assertFalse(body["store"])

    def test_category_suggestion_must_be_an_existing_category(self):
        from unittest.mock import Mock, patch
        from django.test import override_settings
        import json
        api_response = Mock()
        api_response.__enter__ = Mock(return_value=api_response)
        api_response.__exit__ = Mock(return_value=False)
        api_response.read.return_value = json.dumps({"output": [{"content": [{"type": "output_text", "text": "sanitation"}]}]}).encode()
        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("issues.ai_assistant.urlopen", return_value=api_response):
                response = self.client.post(self.url, data=json.dumps({"action":"category", "description":"A blocked drain"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "sanitation")

    def test_provider_failure_returns_friendly_fallback(self):
        from unittest.mock import patch
        from django.test import override_settings
        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("issues.ai_assistant.urlopen", side_effect=TimeoutError):
                response = self.client.post(self.url, data='{"action":"summary","description":"blocked drain"}', content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("continue entering the report manually", response.json()["error"])

    def test_ai_endpoint_requires_login_and_validates_input(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, data="{}", content_type="application/json").status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(self.url, data='{"action":"unknown","description":"test"}', content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_language_switcher_sets_supported_locale(self):
        response = self.client.post(reverse("set_language"), {"language": "hi", "next": "/"})
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/", HTTP_COOKIE=f"django_language=hi")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "समस्या दर्ज करें")




