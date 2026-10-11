from rest_framework import permissions, viewsets
from django.utils import timezone

from .models import Issue
from .serializers import IssueSerializer
from .services import route_issue_department


class IssuePermission(permissions.BasePermission):
    """Everyone may read public reports; owners and staff may edit them."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff or obj.reported_by_id == request.user.id


class IssueViewSet(viewsets.ModelViewSet):
    serializer_class = IssueSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IssuePermission)

    def get_queryset(self):
        issues = Issue.objects.select_related("department", "reported_by").prefetch_related("upvoted_by")
        category = self.request.query_params.get("category")
        status = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        if category:
            issues = issues.filter(category=category)
        if status:
            issues = issues.filter(status=status)
        if priority:
            issues = issues.filter(priority=priority)
        return issues

    def perform_create(self, serializer):
        issue = serializer.save(reported_by=self.request.user)
        route_issue_department(issue)
        issue.save(update_fields=("department", "updated_at"))
        issue.log_history("created", actor=self.request.user, note="Issue reported via API")

    def perform_update(self, serializer):
        issue = serializer.instance
        old_status, old_priority = issue.status, issue.priority
        issue = serializer.save()
        if issue.status != old_status:
            issue.resolved_at = timezone.now() if issue.status == "resolved" else None
            issue.save(update_fields=("resolved_at", "updated_at"))
            issue.log_history("status_changed", actor=self.request.user, note=f"Status changed to {issue.get_status_display()} via API")
        if issue.priority != old_priority:
            issue.log_history("priority_changed", actor=self.request.user, note=f"Priority changed to {issue.get_priority_display()} via API")
