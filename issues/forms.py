from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
import re
from .models import Issue, Profile, Department, PRIORITY_CHOICES, UserSettings, WatchArea, SupportTicket, SupportReply
from django.core.exceptions import ValidationError


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleImageField, self).clean(item, initial) for item in files]


# -----------------------------
# Signup Form
# -----------------------------
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if self.is_bound and self.errors.get(name):
                field.widget.attrs["class"] += " is-invalid"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class CivicAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        invalid = " is-invalid" if self.is_bound and self.non_field_errors() else ""
        self.fields["username"].widget.attrs.update({"class": "form-control" + invalid, "autocomplete": "username"})
        self.fields["password"].widget.attrs.update({"class": "form-control" + invalid, "autocomplete": "current-password"})

    def clean(self):
        username = self.data.get(self.add_prefix("username"), "").strip()
        if "@" in username:
            account_name = User.objects.filter(email__iexact=username).values_list("username", flat=True).first()
            if account_name:
                self.cleaned_data["username"] = account_name
        return super().clean()


# -----------------------------
# Report Issue Form
# -----------------------------
class IssueForm(forms.ModelForm):
    priority = forms.ChoiceField(choices=PRIORITY_CHOICES, required=False, initial="medium")
    photo = forms.ImageField(
        required=False,
        help_text="Add a clear photo if it helps explain the issue (maximum 5 MB).",
        widget=forms.FileInput(attrs={"accept": "image/*"}),
    )
    photos = MultipleImageField(required=False, widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp,image/gif", "multiple": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = Issue
        fields = [
            "title",
            "description",
            "category",
            "priority",
            "latitude",
            "longitude",
            "address",
            "photo",
        ]

        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "For example: Streetlight out near the bus stop"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "latitude": forms.HiddenInput(attrs={"id": "id_latitude"}),
            "longitude": forms.HiddenInput(attrs={"id": "id_longitude"}),
        }

    def clean_priority(self):
        return self.cleaned_data.get("priority") or "medium"

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get("latitude"), cleaned.get("longitude")
        if lat is None or lng is None or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise ValidationError("Choose a valid location on the map before submitting.")
        photo = cleaned.get("photo")
        if photo and photo.size > 5 * 1024 * 1024:
            self.add_error("photo", "Choose an image smaller than 5 MB.")
        uploads = self.cleaned_data.get("photos", [])
        if len(uploads) > 5:
            self.add_error("photos", "Choose no more than 5 photos.")
        for upload in uploads:
            if upload.size > 5 * 1024 * 1024:
                self.add_error("photos", "Each image must be smaller than 5 MB.")
            if upload.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                self.add_error("photos", "Use a JPEG, PNG, WebP, or GIF image.")
        return cleaned


# -----------------------------
# Profile Form
# -----------------------------
class ProfileForm(forms.ModelForm):

    full_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Full Name"
        })
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Email Address"
        })
    )

    avatar = forms.ImageField(
        required=False,
        label="Profile Photo",
        help_text="Choose an image smaller than 2 MB.",
        widget=forms.FileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = Profile
        fields = [
            "avatar",
            "phone",
        ]

        widgets = {
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+91 XXXXXXXXXX",
                "maxlength": "13",
            })
        }

    def __init__(self, *args, **kwargs):

        user = kwargs.pop("user", None)
        self.user = user

        super().__init__(*args, **kwargs)

        if user:
            self.fields["full_name"].initial = user.get_full_name()
            self.fields["email"].initial = user.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        matches = User.objects.filter(email__iexact=email)
        if self.user:
            matches = matches.exclude(pk=self.user.pk)
        if matches.exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return None

        # Remove spaces
        phone = phone.replace(" ", "")

        # Remove +91 if user entered it
        if phone.startswith("+91"):
            phone = phone[3:]

        # Validate exactly 10 digits
        if not re.fullmatch(r"\d{10}", phone):
            raise forms.ValidationError(
                "Enter a valid Indian mobile number."
            )

        # Save in database as +91XXXXXXXXXX
        return "+91" + phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Choose a profile image smaller than 2 MB.")
        return avatar

    def save(self, user, commit=True):

        profile = super().save(commit=False)

        names = self.cleaned_data["full_name"].strip().split(maxsplit=1)

        user.first_name = names[0] if names else ""
        user.last_name = names[1] if len(names) > 1 else ""

        email_changed = user.email.strip().lower() != self.cleaned_data["email"].strip().lower()
        if email_changed:
            profile.email_verified = False
        user.email = self.cleaned_data["email"].strip()

        if commit:
            user.save()
            profile.save()

        return profile


# -----------------------------
# Contact Form
# -----------------------------
class ContactForm(forms.Form):

    name = forms.CharField(max_length=100)

    email = forms.EmailField()

    subject = forms.CharField(max_length=150)

    message = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 5})
    )


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["locality", "preferred_category", "timezone", "language", "theme", "in_app_notifications", "email_notifications", "issue_updates", "area_alerts"]
        widgets = {
            "locality": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
            "preferred_category": forms.Select(attrs={"class": "form-select"}),
            "timezone": forms.Select(choices=[(zone, zone) for zone in ("Asia/Kolkata", "UTC", "Asia/Dubai", "Europe/London", "America/New_York", "America/Los_Angeles")], attrs={"class": "form-select"}),
            "language": forms.Select(attrs={"class": "form-select"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
        }


class WatchAreaForm(forms.ModelForm):
    class Meta:
        model = WatchArea
        fields = ["locality", "category"]
        widgets = {"locality": forms.TextInput(attrs={"class": "form-control", "maxlength": 120, "placeholder": "e.g. Unit 4, Bhubaneswar"}), "category": forms.Select(attrs={"class": "form-select"})}

    def clean_locality(self):
        locality = " ".join(self.cleaned_data["locality"].split())
        if not locality:
            raise forms.ValidationError("Enter a locality to follow.")
        return locality


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["category", "subject", "message", "attachment"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "maxlength": 150}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 5, "maxlength": 5000}),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}),
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            if attachment.size > 5 * 1024 * 1024:
                raise forms.ValidationError("The screenshot must be smaller than 5 MB.")
            if attachment.content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise forms.ValidationError("Upload a JPEG, PNG, or WebP screenshot.")
        return attachment


class SupportReplyForm(forms.ModelForm):
    class Meta:
        model = SupportReply
        fields = ["message"]
        widgets = {"message": forms.Textarea(attrs={"class": "form-control", "rows": 4, "maxlength": 5000})}


# -----------------------------
# Department Assignment
# -----------------------------
class DepartmentAssignForm(forms.ModelForm):

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="— Unassigned —"
    )

    class Meta:
        model = Issue
        fields = ["department"]

from django import forms


