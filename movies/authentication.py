from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            User = get_user_model()
            matching_usernames = list(
                User._default_manager.filter(email__iexact=username)
                .order_by("pk")
                .values_list("username", flat=True)[:2]
            )
            if len(matching_usernames) != 1:
                return None
            username = matching_usernames[0]

        return super().authenticate(
            request,
            username=username,
            password=password,
            **kwargs,
        )
