from rest_framework import viewsets, permissions, status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Issue, haversine_meters
from .serializers import IssueSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.reported_by == request.user


class IssueViewSet(viewsets.ModelViewSet):
    """
    Full REST API for civic issues.

    Extra endpoints:
      GET  /api/issues/nearby/?lat=..&lng=..&radius=500   -> issues within radius (meters)
      POST /api/issues/{id}/upvote/                       -> toggle upvote for current user
      POST /api/issues/{id}/resolve/                      -> mark resolved (owner or staff only)
    """
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        status_param = self.request.query_params.get("status")
        if category:
            qs = qs.filter(category=category)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    @action(detail=False, methods=["get"])
    def nearby(self, request):
        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lng query params are required."}, status=http_status.HTTP_400_BAD_REQUEST)
        radius = float(request.query_params.get("radius", 500))

        results = [
            issue for issue in self.get_queryset()
            if haversine_meters(lat, lng, issue.latitude, issue.longitude) <= radius
        ]
        serializer = self.get_serializer(results, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def upvote(self, request, pk=None):
        issue = self.get_object()
        if request.user in issue.upvoted_by.all():
            issue.upvoted_by.remove(request.user)
            upvoted = False
        else:
            issue.upvoted_by.add(request.user)
            upvoted = True
        return Response({"upvoted": upvoted, "upvote_count": issue.upvote_count})

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        issue = self.get_object()
        if issue.reported_by != request.user and not request.user.is_staff:
            return Response({"detail": "Not permitted."}, status=http_status.HTTP_403_FORBIDDEN)
        issue.mark_resolved()
        return Response(self.get_serializer(issue).data)
