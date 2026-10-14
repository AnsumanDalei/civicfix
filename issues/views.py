import json
import logging
import os
import hashlib
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.utils.dateparse import parse_date
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.http import FileResponse, Http404
import mimetypes
from django.db import transaction
from django.utils.translation import activate
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from .forms import (
    SignUpForm,
    IssueForm,
    ProfileForm,
    ContactForm,
    DepartmentAssignForm,
    UserSettingsForm,
    WatchAreaForm,
    SupportTicketForm,
    SupportReplyForm,
)
from .models import Issue, CATEGORY_CHOICES, STATUS_CHOICES, PRIORITY_CHOICES, Department, Notification, IssueFollow, IssueComment, IssuePhoto, haversine_meters, UserSettings, WatchArea, SupportTicket, SupportReply, AccountDeletionRequest, ContactMessage
from .services import route_issue_department
from .ai_assistant import assist_with_issue
logger = logging.getLogger("issues")


def notify_user(user, message, issue=None):
    preferences = UserSettings.objects.filter(user=user).only("in_app_notifications").first()
    if preferences is None or preferences.in_app_notifications:
        return Notification.objects.create(user=user, issue=issue, message=message[:255])
    return None

def _send_verification_email(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    verify_url = request.build_absolute_uri(
        reverse("verify_email", args=[uid, token])
    )

    send_mail(
        subject="Verify your CivicFix Email",
        message=f"""
Hi {user.username},

Please verify your email by clicking the link below:

{verify_url}

If you did not create this account, ignore this email.
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def is_staff(user):
    return user.is_staff


class CivicLoginView(LoginView):
    """Send residents home after login and staff to their operations queue."""

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        return reverse("staff_operations" if self.request.user.is_staff else "landing")


# Auth: signup + email verification

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                _send_verification_email(request, user)
            except Exception:
                logger.exception("Failed to send signup verification email for user %s", user.pk)
            logger.info("New user signed up: %s", user.username)
            messages.success(
                request,
                "Account created successfully. Please log in to continue.",
            )
            return redirect("login")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})



def verify_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.profile.email_verified = True
        user.profile.save()
        messages.success(request, "Email verified. Thanks!")
    else:
        messages.error(request, "That verification link is invalid or has expired.")
    return redirect("landing" if request.user.is_authenticated else "login")


@login_required
@require_POST
def resend_verification_view(request):
    try:
        _send_verification_email(request, request.user)
    except Exception:
        logger.exception("Failed to resend verification email for user %s", request.user.pk)
        messages.error(request, "We could not send the verification email right now. Please try again later.")
    else:
        messages.info(request, "Verification email resent.")
    return redirect("profile")


# Core pages

def landing_view(request):
    total = Issue.objects.count()
    resolved = Issue.objects.filter(status="resolved").count()
    stats = {"total": total, "resolved": resolved,
             "open": Issue.objects.exclude(status="resolved").count(),
             "in_progress": Issue.objects.filter(status="in_progress").count(),
             "resolution_rate": round(resolved * 100 / total) if total else 0}
    recent = Issue.objects.select_related("department").annotate(supports=Count("upvoted_by", distinct=True)).order_by("-created_at")[:4]
    points = list(Issue.objects.order_by("-created_at").values("id", "title", "category", "status", "latitude", "longitude")[:50])
    return render(request, "issues/landing.html", {"stats": stats, "recent_issues": recent, "map_points": points})


@login_required
@user_passes_test(is_staff)
def staff_operations_view(request):
    priority_order = Case(When(priority="high", then=Value(0)), When(priority="medium", then=Value(1)), default=Value(2), output_field=IntegerField())
    active = Issue.objects.exclude(status="resolved").select_related("department", "reported_by").order_by(priority_order, "created_at")
    return render(request, "issues/staff_operations.html", {
        "new_count": Issue.objects.filter(status="open").count(),
        "unassigned_count": active.filter(department__isnull=True).count(),
        "in_progress_count": Issue.objects.filter(status="in_progress").count(),
        "resolved_count": Issue.objects.filter(status="resolved").count(),
        "queue": active[:12],
    })


@login_required
@require_POST
def ai_assist_view(request):
    """Ask for an optional suggestion using only the submitted report text."""
    try:
        payload = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    action = payload.get("action") if isinstance(payload, dict) else None
    description = payload.get("description", "") if isinstance(payload, dict) else ""
    if action not in {"improve", "category", "summary"}:
        return JsonResponse({"error": "Choose a valid AI assist action."}, status=400)
    if not isinstance(description, str) or not description.strip():
        return JsonResponse({"error": "Enter an issue description first."}, status=400)
    if len(description) > 2000:
        return JsonResponse({"error": "Keep the description under 2,000 characters."}, status=400)
    try:
            result = assist_with_issue(action, description.strip())
    except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    if action == "category":
        return JsonResponse({"result": result, "category": result})
    return JsonResponse({"result": result})


def about_view(request):
    return render(request, "issues/about.html")


def contact_view(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            # Save every valid message first, so it is never lost if email delivery fails.
            contact_message = ContactMessage.objects.create(
                name=name, email=email, subject=subject, message=message
            )
            contact_recipient = settings.CONTACT_RECEIVER_EMAIL
            if not contact_recipient:
                messages.error(request, "The contact inbox is not configured yet. Please try again later.")
                return redirect("contact")
            body = f"""
            New Contact Form Submission

            Name: {name}
            Email: {email}
            Subject: {subject}
            Submitted: {timezone.localtime():%Y-%m-%d %H:%M %Z}

            ----------------------------------------

            Message:

            {message}
            """
            try:
                brevo_api_key = os.environ.get("BREVO_API_KEY", "").strip()
                resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()

                if brevo_api_key:
                    # Brevo HTTPS API works on Render Free, where outbound SMTP is blocked.
                    payload = json.dumps({
                        "sender": {
                            "name": "CivicFix Team",
                            "email": os.environ.get(
                                "BREVO_SENDER_EMAIL",
                                "civicfix.team@gmail.com",
                            ).strip(),
                        },
                        "to": [{"email": contact_recipient}],
                        "replyTo": {"email": email, "name": name},
                        "subject": f"[CivicFix Contact] {subject}",
                        "textContent": body,
                    }).encode("utf-8")
                    api_request = Request(
                        "https://api.brevo.com/v3/smtp/email",
                        data=payload,
                        headers={
                            "api-key": brevo_api_key,
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "User-Agent": "CivicFix/1.0",
                        },
                        method="POST",
                    )
                    with urlopen(api_request, timeout=15) as api_response:
                        if not 200 <= api_response.status < 300:
                            raise RuntimeError("Brevo API returned a non-success response")
                elif resend_api_key:
                    payload = json.dumps({
                        "from": os.environ.get(
                            "RESEND_FROM_EMAIL", "CivicFix <onboarding@resend.dev>"
                        ).strip(),
                        "to": [contact_recipient],
                        "reply_to": email,
                        "subject": f"[CivicFix Contact] {subject}",
                        "text": body,
                    }).encode("utf-8")
                    api_request = Request(
                        "https://api.resend.com/emails",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {resend_api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "CivicFix/1.0",
                        },
                        method="POST",
                    )
                    with urlopen(api_request, timeout=10) as api_response:
                        if not 200 <= api_response.status < 300:
                            raise RuntimeError("Resend API returned a non-success response")
                else:
                    # SMTP is retained for local/paid hosting, with a timeout to avoid worker hangs.
                    send_mail(
                        f"[CivicFix Contact] {subject}", body, settings.DEFAULT_FROM_EMAIL,
                        [contact_recipient], fail_silently=False,
                        connection=None,
                    )
                logger.info("Contact form submission %s email accepted by provider for %s", contact_message.pk, contact_recipient)
                messages.success(request, "Thanks — your message has been received. We'll get back to you soon.")
            except HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                logger.error(
                    "Email provider API returned HTTP %s: %s",
                    exc.code,
                    error_body[:2000],
                )
                logger.error("Contact form submission %s saved, but email delivery failed.", contact_message.pk)
                messages.warning(request, "Your message was saved successfully, but email delivery is delayed. Our team can still view it.")
            except Exception:
                logger.exception("Contact form submission %s saved, but email delivery failed", contact_message.pk)
                messages.warning(request, "Your message was saved successfully, but email delivery is delayed. Our team can still view it.")
            return redirect("contact")
    else:
        form = ContactForm()
    return render(request, "issues/contact.html", {"form": form})

def privacy_view(request):
    return render(request, "issues/privacy.html")


def terms_view(request):
    return render(request, "issues/terms.html")


def faq_view(request):
    return render(request, "issues/faq.html")


# Issue CRUD





@login_required
@require_http_methods(["GET"])
def geocode_view(request):
    """Address lookup through a configurable Nominatim-compatible service.
    Results are cached and the public OSM service is throttled to its published
    one-request-per-second ceiling. An installation may point to its own host."""
    query = request.GET.get("q", "").strip()[:120]
    mode = request.GET.get("mode", "search")
    try:
        if mode == "reverse":
            lat, lng = float(request.GET.get("lat", "")), float(request.GET.get("lng", ""))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
            params = {"lat": lat, "lon": lng}
            endpoint = "/reverse"
            cache_value = f"rev:{lat:.5f}:{lng:.5f}"
        else:
            if len(query) < 3:
                return JsonResponse({"results": [], "error": "Enter at least 3 characters."}, status=400)
            params = {"q": query, "limit": 5}
            endpoint = "/search"
            cache_value = f"search:{query.casefold()}"
    except (ValueError, TypeError):
        return JsonResponse({"results": [], "error": "Choose a valid address or map location."}, status=400)
    cache_key = "geocode:" + hashlib.sha256(cache_value.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)
    base = settings.GEOCODING_BASE_URL
    if urlparse(base).scheme != "https" and not settings.DEBUG:
        return JsonResponse({"results": [], "error": "Geocoding is not configured securely."}, status=503)
    # Shared-cache lock avoids exceeding public Nominatim's request rate.
    if not cache.add("geocoding-provider-throttle", True, timeout=1):
        return JsonResponse({"results": [], "error": "Please wait a moment before searching again."}, status=429)
    try:
        params["format"] = "jsonv2"
        headers = {"User-Agent": settings.GEOCODING_USER_AGENT, "Accept": "application/json"}
        contact = os.environ.get("GEOCODING_CONTACT_EMAIL", "")
        if contact:
            params["email"] = contact
        req = Request(f"{base}{endpoint}?{urlencode(params)}", headers=headers)
        with urlopen(req, timeout=5) as response:
            payload = json.loads(response.read(512 * 1024).decode("utf-8"))
        if mode == "reverse":
            results = [{"lat": payload.get("lat"), "lon": payload.get("lon"), "display_name": payload.get("display_name", "")}] if payload.get("lat") else []
        else:
            results = [{"lat": item.get("lat"), "lon": item.get("lon"), "display_name": item.get("display_name", "")} for item in payload]
        result = {"results": results, "attribution": "© OpenStreetMap contributors"}
        cache.set(cache_key, result, 60 * 60 * 24)
        return JsonResponse(result)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        logger.info("Geocoding provider unavailable", exc_info=True)
        return JsonResponse({"results": [], "error": "Address search is temporarily unavailable. Place the pin manually."}, status=503)








@login_required
def report_issue_view(request):
    if request.method == "POST":
        form = IssueForm(request.POST, request.FILES)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reported_by = request.user
            photos = form.cleaned_data.get("photos", [])
            primary_from_gallery = bool(photos and not issue.photo)
            if primary_from_gallery:
                issue.photo = photos[0]
            dup = issue.find_possible_duplicate() if request.POST.get("allow_duplicate") != "1" else None
            if dup:
                return render(request, "issues/report_form.html", {
                    "form": form, "possible_duplicate": dup,
                    "duplicate_distance": round(haversine_meters(issue.latitude, issue.longitude, dup.latitude, dup.longitude)),
                    "default_map_lat": issue.latitude, "default_map_lng": issue.longitude,
                    "default_map_zoom": 15,
                })

            route_issue_department(issue)
            issue.save()
            for image in photos[1:] if primary_from_gallery else photos:
                IssuePhoto(issue=issue, image=image).save()
            issue.log_history("created", actor=request.user, note="Issue reported")
            if issue.department:
                issue.log_history("assigned", actor=None, note=f"Automatically routed to {issue.department}")

            if issue.address:
                areas = WatchArea.objects.filter(Q(category="") | Q(category=issue.category)).exclude(locality="").select_related("user")
                for area in areas:
                    if area.user_id != request.user.id and area.locality.casefold() in issue.address.casefold():
                        preferences = UserSettings.objects.filter(user_id=area.user_id).only("in_app_notifications", "area_alerts").first()
                        if preferences is None or (preferences.in_app_notifications and preferences.area_alerts):
                            Notification.objects.get_or_create(
                                user_id=area.user_id, issue=issue,
                                message=f"A new issue was reported in {area.locality}.", is_read=False,
                            )

            logger.info("Issue #%s created by %s", issue.pk, request.user.username)
            messages.success(request, "Issue reported successfully. Thank you!")
            return redirect("issue_detail", pk=issue.pk)
    else:
        form = IssueForm()
        preferred_category = UserSettings.objects.filter(user=request.user).values_list("preferred_category", flat=True).first()
        if preferred_category:
            form.fields["category"].initial = preferred_category
    context = {
        "form": form,
        "default_map_lat": settings.DEFAULT_MAP_LAT,
        "default_map_lng": settings.DEFAULT_MAP_LNG,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM,
    }
    return render(request, "issues/report_form.html", context)


@login_required
def issue_edit_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if issue.reported_by != request.user and not request.user.is_staff:
        messages.error(request, "You can only edit issues you reported.")
        return redirect("issue_detail", pk=pk)

    if request.method == "POST":
        form = IssueForm(request.POST, request.FILES, instance=issue)
        if form.is_valid():
            issue = form.save()
            for image in form.cleaned_data.get("photos", []):
                IssuePhoto(issue=issue, image=image).save()
            issue.log_history("edited", actor=request.user, note="Issue details updated")
            logger.info("Issue #%s edited by %s", issue.pk, request.user.username)
            messages.success(request, "Issue updated.")
            return redirect("issue_detail", pk=pk)
    else:
        form = IssueForm(instance=issue)

    context = {
        "form": form,
        "editing": True,
        "issue": issue,
        "default_map_lat": issue.latitude,
        "default_map_lng": issue.longitude,
        "default_map_zoom": 15,
    }
    return render(request, "issues/report_form.html", context)


@login_required
def issue_delete_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if issue.reported_by != request.user and not request.user.is_staff:
        messages.error(request, "You can only delete issues you reported.")
        return redirect("issue_detail", pk=pk)

    if request.method == "POST":
        title = issue.title
        issue.delete()
        logger.info("Issue '%s' (#%s) deleted by %s", title, pk, request.user.username)
        messages.success(request, f"'{title}' was deleted.")
        return redirect("issue_list")

    return render(request, "issues/issue_confirm_delete.html", {"issue": issue})


def issue_list_view(request):
    qs = Issue.objects.select_related("department").annotate(supports=Count("upvoted_by", distinct=True))

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category")
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    department = request.GET.get("department", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    sort = request.GET.get("sort", "recent")

    if query:
        search = Q(title__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query) | Q(category__icontains=query) | Q(department__name__icontains=query)
        normalized_id = query.upper().removeprefix("CF-").removeprefix("#").strip()
        if normalized_id.isdigit():
            search |= Q(pk=int(normalized_id))
        qs = qs.filter(search)
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    if department == "unassigned":
        qs = qs.filter(department__isnull=True, status__in=("open", "in_progress"))
    elif department.isdigit():
        qs = qs.filter(department_id=int(department))
    parsed_from, parsed_to = parse_date(date_from), parse_date(date_to)
    if parsed_from:
        qs = qs.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        qs = qs.filter(created_at__date__lte=parsed_to)
    if priority in dict(PRIORITY_CHOICES):
        qs = qs.filter(priority=priority)
    if sort == "priority":
        priority_order = Case(When(priority="high", then=Value(0)), When(priority="medium", then=Value(1)), default=Value(2), output_field=IntegerField())
        qs = qs.order_by(priority_order, "created_at")
    else:
        ordering = {"recent": "-created_at", "oldest": "created_at", "supported": "-supports"}.get(sort, "-created_at")
        qs = qs.order_by(ordering)
    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    return render(request, "issues/issue_list.html", {
        "page_obj": page_obj,
        "categories": CATEGORY_CHOICES,
        "statuses": STATUS_CHOICES,
        "priorities": PRIORITY_CHOICES,
        "selected_category": category,
        "selected_status": status,
        "selected_priority": priority,
        "selected_sort": sort,
        "query": query,
        "departments": Department.objects.all(),
        "selected_department": department,
        "date_from": date_from,
        "date_to": date_to,
    })


def issue_detail_view(request, pk):
    issue = get_object_or_404(
        Issue.objects.select_related("department", "reported_by").prefetch_related("upvoted_by"),
        pk=pk,
    )
    departments = Department.objects.all()
    assign_form = DepartmentAssignForm(instance=issue) if request.user.is_staff else None
    return render(request, "issues/issue_detail.html", {
        "issue": issue,
        "departments": departments,
        "assign_form": assign_form,
        "priority_choices": PRIORITY_CHOICES,
        "history": issue.history.select_related("actor").order_by("created_at", "pk"),
        "is_following": request.user.is_authenticated and IssueFollow.objects.filter(issue=issue, user=request.user).exists(),
        "comments": issue.comments.filter(is_hidden=False).select_related("user"),
        "gallery_photos": issue.photos.all(),
        "helpful_updates": issue.comments.filter(is_hidden=False, is_helpful=True).count(),
            })


@login_required
@require_POST
def follow_issue_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    follow, created = IssueFollow.objects.get_or_create(issue=issue, user=request.user)
    if not created:
        follow.delete()
        messages.info(request, "You will no longer receive updates about this issue.")
    else:
        messages.success(request, "You are now following this issue and will receive updates.")
    return redirect("issue_detail", pk=pk)


@login_required
@require_POST
def add_issue_comment_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    body = request.POST.get("body", "").strip()
    if not body or len(body) > 1000:
        messages.error(request, "Write an update between 1 and 1,000 characters.")
    elif IssueComment.objects.filter(issue=issue, user=request.user, created_at__gte=timezone.now()-timedelta(seconds=30)).exists():
        messages.error(request, "Please wait a moment before posting another update.")
    else:
        IssueComment.objects.create(issue=issue, user=request.user, body=body)
        issue.log_history("commented", actor=request.user, note="Community update added")
        messages.success(request, "Your community update was posted.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
@require_POST
def hide_issue_comment_view(request, pk, comment_pk):
    comment = get_object_or_404(IssueComment, pk=comment_pk, issue_id=pk)
    comment.is_hidden = True
    comment.save(update_fields=["is_hidden"])
    messages.success(request, "Community update hidden from public view.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
@require_POST
def mark_comment_helpful_view(request, pk, comment_pk):
    comment = get_object_or_404(IssueComment, pk=comment_pk, issue_id=pk, is_hidden=False)
    if not comment.is_helpful:
        comment.is_helpful = True
        comment.save(update_fields=["is_helpful"])
        if comment.user_id != request.user.id:
            Notification.objects.get_or_create(user_id=comment.user_id, issue_id=pk, message=f'An authority marked your update on "{comment.issue.title}" helpful.')
    return redirect("issue_detail", pk=pk)


def issue_map_view(request):
    points = Issue.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True).values(
        "id", "title", "category", "status", "priority", "latitude", "longitude", "address", "created_at"
    )[:1000]
    return render(request, "issues/issue_map.html", {"categories": CATEGORY_CHOICES, "statuses": STATUS_CHOICES, "priorities": PRIORITY_CHOICES, "map_points": [
        {**p, "created_at": p["created_at"].strftime("%Y-%m-%d")} for p in points
    ]})


@login_required
@require_POST
def upvote_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.user in issue.upvoted_by.all():
        issue.upvoted_by.remove(request.user)
        messages.info(request, "Upvote removed.")
    else:
        issue.upvoted_by.add(request.user)
        messages.success(request, "Your support was recorded.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
def assign_department_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.method == "POST":
        form = DepartmentAssignForm(request.POST, instance=issue)
        if form.is_valid():
            form.save()
            issue.log_history(
                "assigned", actor=request.user,
                note=f"Assigned to {issue.department}" if issue.department else "Unassigned",
            )
            logger.info("Issue #%s assigned to %s by %s", issue.pk, issue.department, request.user.username)
            messages.success(request, "Department assignment updated.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
def mark_resolved_view(request, pk):
    if request.method != "POST":
        return redirect("issue_detail", pk=pk)
    issue = get_object_or_404(Issue, pk=pk)
    note = request.POST.get("resolution_note", "").strip()
    if not note:
        messages.error(request, "Add a short note describing the resolution before closing this case.")
        return redirect("issue_detail", pk=pk)
    issue.mark_resolved(actor=request.user, note=note)
    logger.info("Issue #%s marked resolved by %s", issue.pk, request.user.username)
    messages.success(request, "Issue marked resolved.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
@require_POST
def update_issue_status_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    status = request.POST.get("status", "")
    note = request.POST.get("status_note", "").strip()
    if not note:
        messages.error(request, "Add a short progress note for the status update.")
    else:
        try:
            changed = issue.update_status(status, request.user, note)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            if changed:
                messages.success(request, "Case status updated.")
            else:
                messages.info(request, "This case already has that status.")
    return redirect("issue_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
@require_POST
def update_issue_priority_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    note = request.POST.get("priority_note", "").strip()
    if not note:
        messages.error(request, "Add a short reason for changing the priority.")
    else:
        try:
            changed = issue.update_priority(request.POST.get("priority", ""), request.user, note)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Priority updated." if changed else "This issue already has that priority.")
    return redirect("issue_detail", pk=pk)


@login_required
@require_POST
def reopen_issue_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if issue.reported_by_id != request.user.id and not request.user.is_staff:
        messages.error(request, "Only the reporter or an authority officer can reopen this issue.")
        return redirect("issue_detail", pk=pk)
    reason = request.POST.get("reason", "").strip()
    if issue.status == "resolved" and not reason:
        messages.error(request, "Tell the authority what still needs attention before reopening this case.")
        return redirect("issue_detail", pk=pk)
    if issue.status == "resolved":
        issue.status = "open"
        issue.resolved_at = None
        issue.save(update_fields=["status", "resolved_at", "updated_at"])
        issue.log_history("status_changed", actor=request.user,
                          note=f"Reopened: {reason[:200]}")
        messages.success(request, "Issue reopened. The authority can review it again.")
    return redirect("issue_detail", pk=pk)


# Profile

@login_required
def settings_view(request):
    preferences, _ = UserSettings.objects.get_or_create(user=request.user)
    watch_form = WatchAreaForm()
    if request.method == "POST":
        form = UserSettingsForm(request.POST, instance=preferences)
        if form.is_valid():
            preferences = form.save()
            activate(preferences.language)
            messages.success(request, "Your settings have been saved.")
            response = redirect("user_settings")
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, preferences.language, max_age=settings.LANGUAGE_COOKIE_AGE)
            return response
    else:
        form = UserSettingsForm(instance=preferences)
    deletion_request = request.user.deletion_requests.filter(status="pending").first()
    return render(request, "issues/settings.html", {
        "form": form,
        "watch_form": watch_form,
        "watch_areas": request.user.watch_areas.all(),
        "tickets": request.user.support_tickets.all()[:5],
        "deletion_request": deletion_request,
        "profile": request.user.profile,
    })


@login_required
@require_POST
def add_watch_area_view(request):
    form = WatchAreaForm(request.POST)
    if form.is_valid():
        area, created = WatchArea.objects.get_or_create(
            user=request.user,
            locality=form.cleaned_data["locality"],
            category=form.cleaned_data["category"],
        )
        messages.success(request, "Area added to your watch list." if created else "That area is already on your watch list.")
    else:
        messages.error(request, "Enter a valid locality and category.")
    return redirect("user_settings")


@login_required
@require_POST
def remove_watch_area_view(request, pk):
    get_object_or_404(WatchArea, pk=pk, user=request.user).delete()
    messages.success(request, "Area removed from your watch list.")
    return redirect("user_settings")


@login_required
def export_user_data_view(request):
    user = request.user
    preferences, _ = UserSettings.objects.get_or_create(user=user)
    payload = {
        "profile": {"username": user.username, "first_name": user.first_name, "last_name": user.last_name,
                    "email": user.email, "phone": user.profile.phone, "email_verified": user.profile.email_verified},
        "preferences": {"locality": preferences.locality, "preferred_category": preferences.preferred_category,
                        "timezone": preferences.timezone, "language": preferences.language, "theme": preferences.theme,
                        "in_app_notifications": preferences.in_app_notifications,
                        "email_notifications": preferences.email_notifications,
                        "issue_updates": preferences.issue_updates, "area_alerts": preferences.area_alerts},
        "watch_areas": list(user.watch_areas.values("locality", "category", "created_at")),
        "reports": list(user.issues.values("id", "title", "description", "category", "status", "priority", "address", "latitude", "longitude", "created_at", "updated_at")),
        "supported_issue_ids": list(user.upvoted_issues.values_list("id", flat=True)),
        "followed_issue_ids": list(user.followed_issues.values_list("issue_id", flat=True)),
        "support_tickets": list(user.support_tickets.values("reference", "category", "subject", "message", "status", "created_at")),
        "notifications": list(user.notifications.values("message", "is_read", "created_at")),
    }
    from django.core.serializers.json import DjangoJSONEncoder
    response = HttpResponse(json.dumps(payload, cls=DjangoJSONEncoder, indent=2), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="civicfix-my-data.json"'
    return response


@login_required
@require_POST
def request_account_deletion_view(request):
    if request.POST.get("confirm_deletion") != "yes":
        messages.error(request, "Confirm the account deletion request before submitting.")
    elif not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Your password did not match. The request was not submitted.")
    else:
        with transaction.atomic():
            AccountDeletionRequest.objects.get_or_create(user=request.user, status="pending")
        messages.success(request, "Your account deletion request is awaiting staff review. Your reports remain available for civic records.")
    return redirect("user_settings")


@login_required
def support_ticket_list_view(request):
    tickets = SupportTicket.objects.filter(requester=request.user)
    return render(request, "issues/support_ticket_list.html", {"tickets": tickets})


@login_required
def support_ticket_create_view(request):
    form = SupportTicketForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.requester = request.user
        ticket.save()
        logger.info("Support ticket %s created by user %s", ticket.reference, request.user.pk)
        messages.success(request, f"Support request {ticket.reference} was submitted.")
        return redirect("support_ticket_detail", pk=ticket.pk)
    return render(request, "issues/support_ticket_form.html", {"form": form})


@login_required
def support_ticket_detail_view(request, pk):
    ticket = get_object_or_404(SupportTicket.objects.prefetch_related("replies__author"), pk=pk)
    if not (request.user.is_staff or ticket.requester_id == request.user.id):
        raise Http404
    reply_form = SupportReplyForm(request.POST or None)
    if request.method == "POST" and reply_form.is_valid():
        with transaction.atomic():
            reply = reply_form.save(commit=False)
            reply.ticket, reply.author = ticket, request.user
            reply.save()
            ticket.save(update_fields=["updated_at"])
            recipient = ticket.requester if request.user.is_staff else None
            if recipient:
                notify_user(recipient, f"A reply was added to support request {ticket.reference}.")
        messages.success(request, "Your reply was added.")
        return redirect("support_ticket_detail", pk=ticket.pk)
    return render(request, "issues/support_ticket_detail.html", {"ticket": ticket, "reply_form": reply_form})


@login_required
def support_attachment_view(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk)
    if not (request.user.is_staff or ticket.requester_id == request.user.id):
        raise Http404
    if not ticket.attachment:
        raise Http404
    try:
        content_type = mimetypes.guess_type(ticket.attachment.name)[0] or "application/octet-stream"
        return FileResponse(ticket.attachment.open("rb"), content_type=content_type)
    except OSError as exc:
        logger.warning("Support attachment unavailable for ticket %s: %s", ticket.reference, exc)
        raise Http404


@login_required
@user_passes_test(is_staff)
def support_admin_view(request):
    if request.method == "POST":
        ticket = get_object_or_404(SupportTicket, pk=request.POST.get("ticket_id"))
        status = request.POST.get("status")
        priority = request.POST.get("priority")
        if status not in dict(SupportTicket._meta.get_field("status").choices) or priority not in dict(SupportTicket._meta.get_field("priority").choices):
            messages.error(request, "Choose a valid ticket status and priority.")
        else:
            ticket.status, ticket.priority = status, priority
            ticket.save(update_fields=["status", "priority", "updated_at"])
            notify_user(ticket.requester, f"Support request {ticket.reference} was updated: {ticket.get_status_display()}.")
            messages.success(request, f"Support request {ticket.reference} was updated.")
        return redirect("support_admin")
    return render(request, "issues/support_admin.html", {
        "tickets": SupportTicket.objects.select_related("requester").all(),
        "deletion_requests": AccountDeletionRequest.objects.select_related("user").filter(status="pending"),
    })


@login_required
@user_passes_test(is_staff)
@require_POST
def review_deletion_request_view(request, pk):
    deletion = get_object_or_404(AccountDeletionRequest, pk=pk, status="pending")
    decision = request.POST.get("decision")
    if decision not in {"approved", "rejected"}:
        messages.error(request, "Choose approve or reject.")
    else:
        deletion.status = decision
        deletion.reviewed_by = request.user
        deletion.reviewed_at = timezone.now()
        deletion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        notify_user(deletion.user, f"Your account deletion request was {decision}.")
        messages.success(request, "Request review recorded. Account data has not been deleted.")
    return redirect("support_admin")

@login_required
def profile_view(request):
    show_edit_modal = False

    if request.method == "POST":

        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=request.user.profile,
            user=request.user
        )

        if form.is_valid():
            email_changed = request.user.email.strip().lower() != form.cleaned_data["email"].strip().lower()

            if "remove_avatar" in request.POST:
                request.user.profile.avatar.delete(save=False)
                request.user.profile.avatar = None
            form.save(user=request.user)

            if email_changed:
                try:
                    _send_verification_email(request, request.user)
                except Exception:
                    logger.exception("Failed to send profile verification email for user %s", request.user.pk)
                    messages.error(request, "Your profile was saved, but we could not send the verification email right now.")
                    return redirect("profile")

            if email_changed:
                messages.success(request, "Profile updated. Check your new email address to verify it.")
            else:
                messages.success(request, "Profile updated successfully.")

            return redirect("profile")

        else:
            show_edit_modal = True
            messages.error(
                request,
                "Please correct the errors below."
            )

    else:

        form = ProfileForm(
            instance=request.user.profile,
            user=request.user
        )

    my_issues = Issue.objects.filter(
        reported_by=request.user
    )
    total_upvotes = sum(issue.upvote_count for issue in my_issues)

    context = {
        "form": form,
        "my_issues": my_issues,
        "resolved_count": my_issues.filter(status="resolved").count(),
        "open_count": my_issues.exclude(status="resolved").count(),
        "in_progress_count": my_issues.filter(status="in_progress").count(),
        "total_upvotes": total_upvotes,
        "supported_issues": Issue.objects.filter(upvoted_by=request.user).select_related("department").distinct()[:8],
        "following_issues": Issue.objects.filter(followers__user=request.user).select_related("department").distinct()[:8],
        "show_edit_modal": show_edit_modal,
    }

    return render(
        request,
        "issues/profile.html",
        context,
    )


# Notifications (polling — see base.html JS)

@login_required
def notifications_api_view(request):
    notifications = request.user.notifications.all()[:15]
    unread_count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.id,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.strftime("%d %b, %H:%M"),
                "issue_id": n.issue_id,
            }
            for n in notifications
        ],
    })


@login_required
@require_POST
def notifications_mark_read_view(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return redirect("notification_center")
    return JsonResponse({"ok": True})


@login_required
def notification_center_view(request):
    notifications = request.user.notifications.select_related("issue")
    paginator = Paginator(notifications, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "issues/notifications.html", {"page_obj": page_obj, })


@login_required
@require_POST
def notification_mark_read_view(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if notification.issue_id:
        return redirect("issue_detail", pk=notification.issue_id)
    return redirect("issue_detail", pk=pk)


# Basic public analytics
def analytics_view(request):
    """Show a few useful counts calculated directly from the issue database."""
    by_category = list(Issue.objects.values("category").annotate(total=Count("id")).order_by("category"))
    by_department = Issue.objects.exclude(department__isnull=True).values("department__name").annotate(total=Count("id")).order_by("-total")
    from django.db.models.functions import TruncMonth
    monthly_rows = Issue.objects.annotate(month=TruncMonth("created_at")).values("month").annotate(total=Count("id")).order_by("month")
    total = Issue.objects.count()
    resolved = Issue.objects.filter(status="resolved").count()
    return render(request, "issues/analytics.html", {
        "by_category": json.dumps(by_category),
        "by_department": by_department,
        "total": total,
        "resolved": resolved,
        "open": Issue.objects.filter(status="open").count(),
        "in_progress": Issue.objects.filter(status="in_progress").count(),
        "resolution_rate": round(resolved * 100 / total) if total else 0,
        "monthly": json.dumps([{"month": row["month"].strftime("%b %Y"), "total": row["total"]} for row in monthly_rows if row["month"]]),
    })






