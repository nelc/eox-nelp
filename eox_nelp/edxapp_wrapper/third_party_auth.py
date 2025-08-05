"""
Wrapper third_party_auth app.

This contains all the required dependencies from third_party_auth app

Attributes:
    backend:Imported third_party_auth app module by using the plugin settings.
    Registry: Registry class for third-party authentication providers.

"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_THIRD_PARTY_AUTH_BACKEND)

Registry = backend.get_registry()
