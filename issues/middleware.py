from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone, translation
from django.conf import settings

from .models import UserSettings


class UserPreferencesMiddleware:
    """Apply persisted language and time zone preferences to authenticated requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            preference = UserSettings.objects.filter(user=user).only("language", "timezone").first()
            if preference:
                session_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
                available = {code for code, _label in settings.LANGUAGES}
                if session_language in available and session_language != preference.language:
                    preference.language = session_language
                    preference.save(update_fields=["language", "updated_at"])
                translation.activate(preference.language)
                try:
                    timezone.activate(ZoneInfo(preference.timezone))
                except (ZoneInfoNotFoundError, ValueError):
                    timezone.activate("Asia/Kolkata")
        response = self.get_response(request)
        if user is not None and user.is_authenticated:
            timezone.deactivate()
            translation.deactivate()
        return response
