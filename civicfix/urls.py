from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.contrib.auth import views as auth_views
from issues import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- Auth (login / logout / signup) ---
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup_view, name="signup"),

    # --- Frontend pages ---
    path("", views.landing_view, name="landing"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("report/", views.report_issue_view, name="report_issue"),
    path("issues/", views.issue_list_view, name="issue_list"),
    path("issues/<int:pk>/", views.issue_detail_view, name="issue_detail"),
    path("issues/<int:pk>/upvote/", views.upvote_view, name="upvote_issue"),
    path("analytics/", views.analytics_view, name="analytics"),

    # --- REST API ---
    path("api/", include("issues.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
