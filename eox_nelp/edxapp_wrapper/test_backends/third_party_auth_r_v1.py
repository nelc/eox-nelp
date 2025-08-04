"""Backend abstraction for third_party_auth."""
from mock import Mock


def get_registry():
    """Return Registry class for third-party authentication providers.

    Returns:
        Mock class.
    """
    return Mock()


def get_models():
    """Return models module for third-party authentication.

    Returns:
        Mock class.
    """
    return Mock()
