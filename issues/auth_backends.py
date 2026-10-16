from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """Allow users to sign in with either their username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("email") or kwargs.get("username")
        if not identifier or password is None:
            return None

        UserModel = get_user_model()
        if "@" in identifier:
            try:
                user = UserModel._default_manager.get(email__iexact=identifier)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                return None
            username = user.get_username()
        else:
            username = identifier

        return super().authenticate(request, username=username, password=password, **kwargs)
