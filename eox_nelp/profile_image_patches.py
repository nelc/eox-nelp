"""
Rate limit for the profile image endpoints of edx-platform.

`POST` / `DELETE /api/user/v1/accounts/{username}/image` (and the two legacy
upload / remove routes) have no throttle in edx-platform, and the LMS sets no
default throttle class, so a logged-in user can send them without limit
(pentest finding H-001).

The patch gives those views a per-user throttle. A view that already declares
its own throttle is left alone, so an upstream fix is never overwritten.
Remove this module once edx-platform throttles these views itself.
"""
import logging
from importlib import import_module

from django.conf import settings
from rest_framework.throttling import UserRateThrottle

logger = logging.getLogger(__name__)

PROFILE_IMAGE_VIEWS_MODULE = "openedx.core.djangoapps.profile_images.views"
PROFILE_IMAGE_VIEW_NAMES = ("ProfileImageView", "ProfileImageUploadView", "ProfileImageRemoveView")
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


def patch_profile_image_throttle():
    """Set `ProfileImageRateThrottle` on the edx-platform profile image views that have no throttle."""
    try:
        views = import_module(PROFILE_IMAGE_VIEWS_MODULE)
    except ImportError:
        return

    for name in PROFILE_IMAGE_VIEW_NAMES:
        view = getattr(views, name, None)

        if view is None:
            logger.warning("%s.%s not found; profile image throttle not applied.", PROFILE_IMAGE_VIEWS_MODULE, name)
        elif not view.throttle_classes:
            view.throttle_classes = (ProfileImageRateThrottle,)
