"""Backend for user_authn app.

This file contains all the necessary dependencies from
https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/openedx/core/djangoapps/user_authn
"""
from openedx.core.djangoapps.user_authn import views  # pylint: disable=import-error
from openedx.core.djangoapps.user_authn.api import form_fields


def get_registration_form_factory():
    """Allow to get the class RegistrationFormFactory from
    https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/openedx/core/djangoapps/user_authn/views/registration_form.py

    Returns:
        RegistrationFormFactory class.
    """
    return views.registration_form.RegistrationFormFactory


def get_views():
    """Allow to get the views module of user_authn
    https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/openedx/core/djangoapps/user_authn/views
    Returns: view module
    """
    return views


def get_registration_extension_form():
    """Allow to get the method get_registration_extension_form from
    https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/openedx/core/djangoapps/user_authn/views/registration_form.py

    Returns:
        get_registration_extension_form method.
    """
    return views.registration_form.get_registration_extension_form


def get_api_form_fields():
    """Allow to get the module form_fields from
    https://github.com/nelc/edx-platform/blob/open-release/redwood.nelp/openedx/core/djangoapps/user_authn/api/form_fields.py

    Returns:
        form_fields module.
    """
    return form_fields
