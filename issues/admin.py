from django.contrib import admin
from .models import Issue, EscalationLog


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "category", "status", "escalation_tier", "sla_deadline", "reported_by", "created_at"]
    list_filter = ["category", "status", "escalation_tier"]
    search_fields = ["title", "description", "address"]


@admin.register(EscalationLog)
class EscalationLogAdmin(admin.ModelAdmin):
    list_display = ["issue", "from_tier", "to_tier", "reason", "created_at"]
