"""
Rate limit for the profile image endpoints of edx-platform.

`POST` / `DELETE /api/user/v1/accounts/{username}/image` (and the two legacy
upload / remove routes) have no throttle in edx-platform, and the LMS sets no
default throttle class, so a logged-in user can send them without limit
(pentest finding H-001).

The patch gives those views a per-user throttle. A view that already declares
its own throttle is left alone, so an upstream fix is never overwritten.
Remove this module once edx-platform throttles these views itself.

`eox_nelp.apps` imports this module while the Django settings are still
loading, so nothing here may read the settings at import time: the throttle
class (Django REST framework) is imported inside the patch function.
"""
import logging
from importlib import import_module

logger = logging.getLogger(__name__)

PROFILE_IMAGE_VIEWS_MODULE = "openedx.core.djangoapps.profile_images.views"
PROFILE_IMAGE_VIEW_NAMES = ("ProfileImageView", "ProfileImageUploadView", "ProfileImageRemoveView")


def patch_profile_image_throttle():
    """Set `ProfileImageRateThrottle` on the edx-platform profile image views that have no throttle."""
    try:
        views = import_module(PROFILE_IMAGE_VIEWS_MODULE)
    except ImportError:
        return

    from eox_nelp.profile_image_throttle import ProfileImageRateThrottle  # pylint: disable=import-outside-toplevel

    for name in PROFILE_IMAGE_VIEW_NAMES:
        view = getattr(views, name, None)

        if view is None:
            logger.warning("%s.%s not found; profile image throttle not applied.", PROFILE_IMAGE_VIEWS_MODULE, name)
        elif not view.throttle_classes:
            view.throttle_classes = (ProfileImageRateThrottle,)
