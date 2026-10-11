"""Small business rules shared by the issue views and API."""

from .models import CategoryRouting


def route_issue_department(issue):
    """Assign the configured department for the issue's category, if any."""
    rule = CategoryRouting.objects.select_related("department").filter(
        category=issue.category
    ).first()
    issue.department = rule.department if rule else None
    return issue.department
