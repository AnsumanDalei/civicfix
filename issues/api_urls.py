from rest_framework.routers import DefaultRouter
from .api_views import IssueViewSet

router = DefaultRouter()
router.register(r"issues", IssueViewSet, basename="issue")

urlpatterns = router.urls
