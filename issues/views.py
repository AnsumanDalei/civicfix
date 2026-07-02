import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import SignUpForm, IssueForm
from .models import Issue, CATEGORY_CHOICES


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to CivicFix! Your account was created.")
            return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


def landing_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    stats = {
        "total": Issue.objects.count(),
        "resolved": Issue.objects.filter(status="resolved").count(),
        "open": Issue.objects.exclude(status="resolved").count(),
    }
    return render(request, "issues/landing.html", {"stats": stats})


@login_required
def dashboard_view(request):
    my_issues = Issue.objects.filter(reported_by=request.user)
    all_open = Issue.objects.exclude(status="resolved")
    top_priority = sorted(all_open, key=lambda i: i.priority_score, reverse=True)[:5]
    overdue = [i for i in all_open if i.is_overdue]
    context = {
        "my_issues": my_issues,
        "top_priority": top_priority,
        "overdue_count": len(overdue),
        "total_open": all_open.count(),
    }
    return render(request, "issues/dashboard.html", context)


@login_required
def report_issue_view(request):
    if request.method == "POST":
        form = IssueForm(request.POST, request.FILES)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reported_by = request.user
            issue.save()

            dup = issue.find_possible_duplicate()
            if dup:
                dup.upvoted_by.add(request.user)
                issue.duplicate_of = dup
                issue.status = "resolved"  # collapse duplicate, don't double-count
                issue.save()
                messages.info(
                    request,
                    f"A similar issue was already reported nearby ('{dup.title}'). "
                    f"We added your upvote to it instead of creating a duplicate.",
                )
                return redirect("issue_detail", pk=dup.pk)

            messages.success(request, "Issue reported successfully. Thank you!")
            return redirect("issue_detail", pk=issue.pk)
    else:
        form = IssueForm()
    context = {
        "form": form,
        "default_map_lat": settings.DEFAULT_MAP_LAT,
        "default_map_lng": settings.DEFAULT_MAP_LNG,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM,
    }
    return render(request, "issues/report_form.html", context)


@login_required
def issue_list_view(request):
    qs = Issue.objects.all()
    category = request.GET.get("category")
    status = request.GET.get("status")
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    issues = sorted(qs, key=lambda i: i.priority_score, reverse=True)
    return render(request, "issues/issue_list.html", {
        "issues": issues,
        "categories": CATEGORY_CHOICES,
        "selected_category": category,
        "selected_status": status,
    })


@login_required
def issue_detail_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    return render(request, "issues/issue_detail.html", {"issue": issue})


@login_required
def upvote_view(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.user in issue.upvoted_by.all():
        issue.upvoted_by.remove(request.user)
        messages.info(request, "Upvote removed.")
    else:
        issue.upvoted_by.add(request.user)
        messages.success(request, "Upvoted — this raises its priority score.")
    return redirect("issue_detail", pk=pk)


@login_required
def analytics_view(request):
    by_category = (
        Issue.objects.values("category")
        .annotate(total=Count("id"), resolved=Count("id", filter=Q(status="resolved")))
        .order_by("category")
    )
    by_tier = Issue.objects.exclude(status="resolved").values("escalation_tier").annotate(total=Count("id"))
    context = {
        "by_category": json.dumps(list(by_category)),
        "by_tier": json.dumps(list(by_tier)),
        "total": Issue.objects.count(),
        "resolved": Issue.objects.filter(status="resolved").count(),
        "escalated": Issue.objects.filter(status="escalated").count(),
    }
    return render(request, "issues/analytics.html", context)
