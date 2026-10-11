from django.contrib import admin
from django.utils import timezone

from .models import (
    CategoryRouting,
    Department,
    Issue,
    IssueComment,
    IssueFollow,
    IssueHistory,
    IssuePhoto,
    Notification,
    Profile,
    UserSettings,
    WatchArea,
    SupportTicket,
    SupportReply,
    AccountDeletionRequest,
)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "priority", "status", "department", "reported_by", "created_at")
    list_filter = ("category", "priority", "status", "department")
    search_fields = ("title", "description", "address", "reported_by__username")
    readonly_fields = ("created_at", "updated_at", "resolved_at")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "reported_by":
            # A reporter may be selected explicitly, or defaults to the staff
            # member saving the issue. Keep the field visible in the form.
            field.required = False
            field.help_text = "Choose a reporter, or leave blank to use your account."
        return field

    def save_model(self, request, obj, form, change):
        previous = Issue.objects.get(pk=obj.pk) if change else None
        if obj.reported_by_id is None:
            obj.reported_by = request.user

        if obj.status == "resolved":
            if previous is None or previous.status != "resolved" or obj.resolved_at is None:
                obj.resolved_at = timezone.now()
        else:
            obj.resolved_at = None

        super().save_model(request, obj, form, change)
        if previous is None:
            obj.log_history("created", actor=request.user, note="Issue added by staff")
        else:
            if previous.department_id != obj.department_id:
                obj.log_history("assigned", actor=request.user, note=f"Assigned to {obj.department}" if obj.department else "Unassigned")
            if previous.priority != obj.priority:
                obj.log_history("priority_changed", actor=request.user, note=f"Priority set to {obj.get_priority_display()}")
            if previous.status != obj.status:
                obj.log_history("status_changed", actor=request.user, note=f"Status changed to {obj.get_status_display()}")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(CategoryRouting)
class CategoryRoutingAdmin(admin.ModelAdmin):
    list_display = ("category", "department")


@admin.register(IssueHistory)
class IssueHistoryAdmin(admin.ModelAdmin):
    list_display = ("issue", "event", "actor", "created_at")
    list_filter = ("event",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "email_verified", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "issue", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("message", "user__username")


@admin.register(IssueFollow)
class IssueFollowAdmin(admin.ModelAdmin):
    list_display = ("issue", "user", "created_at")



@admin.register(IssueComment)
class IssueCommentAdmin(admin.ModelAdmin):
    list_display = ("issue", "user", "created_at", "is_hidden")
    list_filter = ("is_hidden", "created_at")



@admin.register(IssuePhoto)
class IssuePhotoAdmin(admin.ModelAdmin):
    list_display = ("issue", "caption", "created_at")


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "theme", "in_app_notifications", "email_notifications")
    search_fields = ("user__username", "user__email")


@admin.register(WatchArea)
class WatchAreaAdmin(admin.ModelAdmin):
    list_display = ("user", "locality", "category", "created_at")
    search_fields = ("user__username", "locality")



class SupportReplyInline(admin.TabularInline):
    model = SupportReply
    extra = 0
    readonly_fields = ("author", "created_at")

    def save_new_instance(self, form, commit=True):
        instance = super().save_new_instance(form, commit=False)
        if not instance.author_id:
            instance.author = self.parent_model
        if commit:
            instance.save()
        return instance




@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "subject",
        "requester",
        "category",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("category", "status", "priority")
    search_fields = (
        "reference",
        "subject",
        "requester__username",
        "requester__email",
    )
    readonly_fields = ("reference", "created_at", "updated_at")
    inlines = [SupportReplyInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            if isinstance(instance, SupportReply) and not instance.author_id:
                instance.author = request.user
            instance.save()

        formset.save_m2m()



@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "reviewed_at", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("user", "reason", "created_at")
