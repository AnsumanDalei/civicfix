from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.contrib.auth import views as auth_views
from issues import views
from issues.forms import CivicAuthenticationForm

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),

    # --- Auth: login / logout / signup / email verification ---
    path("login/", views.CivicLoginView.as_view(template_name="registration/login.html", authentication_form=CivicAuthenticationForm), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("verify-email/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify_email"),
    path("verify-email/resend/", views.resend_verification_view, name="resend_verification"),

    # --- Auth: forgot password (Django's built-in flow) ---
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
    ), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),

    # --- Auth: change password (while logged in) ---
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html",
    ), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html",
    ), name="password_change_done"),

    # --- Frontend pages ---
    path("", views.landing_view, name="landing"),
    path("about/", views.about_view, name="about"),
    path("contact/", views.contact_view, name="contact"),
    path("privacy/", views.privacy_view, name="privacy"),
    path("terms/", views.terms_view, name="terms"),
    path("faq/", views.faq_view, name="faq"),
    path("staff/", views.staff_operations_view, name="staff_operations"),
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="user_settings"),
    path("settings/watch-areas/add/", views.add_watch_area_view, name="watch_area_add"),
    path("settings/watch-areas/<int:pk>/remove/", views.remove_watch_area_view, name="watch_area_remove"),
    path("settings/data-export/", views.export_user_data_view, name="user_data_export"),
    path("settings/account-deletion/", views.request_account_deletion_view, name="account_deletion_request"),
    path("support/", views.support_ticket_list_view, name="support_ticket_list"),
    path("support/new/", views.support_ticket_create_view, name="support_ticket_create"),
    path("support/<int:pk>/", views.support_ticket_detail_view, name="support_ticket_detail"),
    path("support/<int:pk>/attachment/", views.support_attachment_view, name="support_attachment"),
    path("staff/support/", views.support_admin_view, name="support_admin"),
    path("staff/account-deletion/<int:pk>/review/", views.review_deletion_request_view, name="review_deletion_request"),

    # --- Issue CRUD ---
    path("report/", views.report_issue_view, name="report_issue"),
    path("api/geocode/", views.geocode_view, name="geocode"),
    path("api/ai-assist/", views.ai_assist_view, name="ai_assist"),
    path("issues/", views.issue_list_view, name="issue_list"),
    path("map/", views.issue_map_view, name="issue_map"),
    path("issues/<int:pk>/", views.issue_detail_view, name="issue_detail"),
    path("issues/<int:pk>/edit/", views.issue_edit_view, name="issue_edit"),
    path("issues/<int:pk>/delete/", views.issue_delete_view, name="issue_delete"),
    path("issues/<int:pk>/upvote/", views.upvote_view, name="upvote_issue"),
    path("issues/<int:pk>/follow/", views.follow_issue_view, name="follow_issue"),
    path("issues/<int:pk>/updates/", views.add_issue_comment_view, name="add_issue_comment"),
    path("issues/<int:pk>/updates/<int:comment_pk>/hide/", views.hide_issue_comment_view, name="hide_issue_comment"),
    path("issues/<int:pk>/updates/<int:comment_pk>/helpful/", views.mark_comment_helpful_view, name="mark_comment_helpful"),
    path("issues/<int:pk>/assign/", views.assign_department_view, name="assign_department"),
    path("issues/<int:pk>/resolve/", views.mark_resolved_view, name="mark_resolved"),
    path("issues/<int:pk>/status/", views.update_issue_status_view, name="update_issue_status"),
    path("issues/<int:pk>/priority/", views.update_issue_priority_view, name="update_issue_priority"),
    path("issues/<int:pk>/reopen/", views.reopen_issue_view, name="reopen_issue"),

    # --- Notifications (polling) ---
    path("api/notifications/", views.notifications_api_view, name="notifications_api"),
    path("api/notifications/mark-read/", views.notifications_mark_read_view, name="notifications_mark_read"),
    path("notifications/", views.notification_center_view, name="notification_center"),
    path("notifications/<int:pk>/read/", views.notification_mark_read_view, name="notification_mark_read"),

    path("analytics/", views.analytics_view, name="analytics"),

    # --- REST API ---
    path("api/", include("issues.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "issues.views_errors.handler404"
handler500 = "issues.views_errors.handler500"
