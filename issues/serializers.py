from rest_framework import serializers
from .models import Issue, EscalationLog


class EscalationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationLog
        fields = ["id", "from_tier", "to_tier", "reason", "created_at"]


class IssueSerializer(serializers.ModelSerializer):
    reported_by = serializers.ReadOnlyField(source="reported_by.username")
    upvote_count = serializers.ReadOnlyField()
    priority_score = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    escalation_logs = EscalationLogSerializer(many=True, read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id", "title", "description", "category", "status",
            "latitude", "longitude", "address",
            "reported_by", "upvote_count", "priority_score", "is_overdue",
            "escalation_tier", "sla_deadline", "duplicate_of",
            "created_at", "updated_at", "resolved_at", "escalation_logs",
        ]
        read_only_fields = ["status", "escalation_tier", "sla_deadline", "duplicate_of"]
