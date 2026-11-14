"""
Throttle for the edx-platform profile image views.

This module imports Django REST framework, which reads the Django settings at
import time. Import it only once the settings are loaded, never at the top of a
module that `eox_nelp.apps` imports. See `eox_nelp.profile_image_patches`.
"""
from django.conf import settings
from rest_framework.throttling import UserRateThrottle

DEFAULT_PROFILE_IMAGE_THROTTLE_RATE = "10/minute"


class ProfileImageRateThrottle(UserRateThrottle):
    """Per-user limit shared by every profile image view."""

    scope = "profile_image"

    def get_rate(self):
        """
        .. setting_name: EOX_NELP_PROFILE_IMAGE_THROTTLE_RATE
        .. setting_default: 10/minute
        .. setting_description: How many profile image uploads and removals one user may send, as a DRF rate.
        """
        return getattr(settings, "EOX_NELP_PROFILE_IMAGE_THROTTLE_RATE", DEFAULT_PROFILE_IMAGE_THROTTLE_RATE)
