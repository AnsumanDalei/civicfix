from rest_framework import serializers

from .models import Issue


class IssueSerializer(serializers.ModelSerializer):
    reported_by = serializers.StringRelatedField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    support_count = serializers.IntegerField(source="upvote_count", read_only=True)

    class Meta:
        model = Issue
        fields = (
            "id", "title", "description", "category", "status", "priority",
            "latitude", "longitude", "address", "photo", "reported_by",
            "support_count", "department", "department_name", "created_at",
            "updated_at", "resolved_at",
        )
        read_only_fields = ("id", "reported_by", "department", "created_at", "updated_at", "resolved_at")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is None or request.method == "POST" or not request.user.is_staff:
            fields["status"].read_only = True
        return fields

    def validate(self, attrs):
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lng = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise serializers.ValidationError("Choose valid latitude and longitude coordinates.")
        return attrs
