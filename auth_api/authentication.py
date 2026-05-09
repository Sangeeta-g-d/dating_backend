from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class BlockedJWTAuthentication(JWTAuthentication):
    """JWT authentication that rejects blocked or inactive users."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.is_active or getattr(user, "is_blocked", False):
            raise AuthenticationFailed(_("User is blocked or inactive."))
        return user
