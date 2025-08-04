"""Backend for accessing third_party_auth modules.

This file provides access to necessary dependencies from
https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/common/djangoapps/third_party_auth.
"""

from common.djangoapps.third_party_auth import models  # pylint: disable=import-error
from common.djangoapps.third_party_auth.provider import Registry  # pylint: disable=import-error


def get_registry():
    """Provides access to the Registry class from third_party_auth.

    This function imports and returns the Registry class, which is used for managing
    third-party authentication providers.

    Returns:
        Registry: The Registry class for third-party authentication providers.
    """
    return Registry


def get_models():
    """Allow to get the module models from
    https://github.com/nelc/edx-platform/blob/open-release/redwood.nelp/common/djangoapps/third_party_auth/models.py

    Returns:
        models module.
    """
    return models
