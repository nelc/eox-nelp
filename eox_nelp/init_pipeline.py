"""
This file contains all the processes that must run after app registration.

Functions:

    run_init_pipeline:
        Executes all initialization processes required before the Django application starts.
        Acts as an entry point to trigger the patching and setup routines defined below.

    patch_user_gender_choices:
        Updates the default Open edX gender field options to include only "Male" and "Female"
        for compatibility with specific business rules.

    set_mako_templates:
        Adds plugin template directories to the Mako configuration to ensure that
        the custom templates are properly discovered at runtime.

    register_xapi_transformers:
        Imports and registers all available xAPI event transformers to enable event tracking.

    update_permissions:
        Adjusts and extends Open edX permission rules to support additional business roles
        and use cases (e.g., data researcher, staff, instructor).

    patch_generate_password:
        Replaces the default `generate_password` implementation from `edx_django_utils`
        with a custom NELP version for improved tenant-specific logic.

    patch_registration_form_factory:
        Overrides the default `RegistrationFormFactory` used in user authentication
        with the custom NELP implementation to support extended registration logic.

    patch_form_fields_getattr:
        Dynamically patches the `form_fields` module to include a custom `__getattr__`
        method, enabling runtime generation of field handlers based on configuration.
"""

import os

from django.utils.translation import gettext_noop


def run_init_pipeline():
    """
    Executes multiple processes that must run before starting the django application.
    """
    patch_user_gender_choices()
    set_mako_templates()
    register_xapi_transformers()
    update_permissions()
    patch_generate_password()
    patch_registration_form_factory()
    patch_form_fields_getattr()


def patch_user_gender_choices():
    """
    This overwrites the available gender choices in order to allow the Male and Female options.
    """
    # pylint: disable=import-outside-toplevel
    # This cannot be at the top of the file since this file is imported the plugin initialization
    # and therefore the settings has not been set yet
    from eox_nelp.edxapp_wrapper.student import UserProfile

    UserProfile.GENDER_CHOICES = (
        ('m', gettext_noop('Male')),
        ('f', gettext_noop('Female')),
    )


def set_mako_templates():
    """This method adds the plugin templates to mako configuration."""
    # pylint: disable=import-outside-toplevel
    # This cannot be at the top of the file since this file is imported on the plugin initialization
    # and therefore the settings has not been set yet
    from eox_nelp import static as static_module
    from eox_nelp.edxapp_wrapper.edxmako import edxmako
    from eox_nelp.payment_notifications import templates as payment_notifications_templates

    module_templates_to_include = [
        static_module,
        payment_notifications_templates,
    ]

    for module in module_templates_to_include:
        path_to_templates = os.path.dirname(module.__file__)

        if path_to_templates not in edxmako.LOOKUP['main'].directories:
            edxmako.paths.add_lookup('main', path_to_templates)


def register_xapi_transformers():
    """This method just import the event transformers in order to register all of them."""
    # pylint: disable=import-outside-toplevel, unused-import
    from eox_nelp.processors.xapi import event_transformers as xapi_event_transformers  # noqa: F401


def update_permissions():
    """This method just change permissions for bussiness cases"""
    # pylint: disable=import-outside-toplevel
    from bridgekeeper import perms
    from bridgekeeper.rules import is_staff

    from eox_nelp.edxapp_wrapper.courseware import rules
    from eox_nelp.edxapp_wrapper.instructor import permissions

    perms.pop(permissions.CAN_RESEARCH, None)
    perms[permissions.CAN_RESEARCH] = (
        is_staff  # pylint: disable=unsupported-binary-operation, useless-suppression
        | rules.HasRolesRule("data_researcher")
        | rules.HasAccessRule("staff")
        | rules.HasAccessRule("instructor")
    )


def patch_generate_password():
    """This method patch `generate_password` of edx_django_util package,
    with custom nelp `generate_password`.
    """
    # pylint: disable=import-outside-toplevel
    from eox_tenant.tenant_wise import set_as_proxy

    from eox_nelp.user_authn.utils import generate_password

    set_as_proxy(
        modules=[
            "lms.djangoapps.support.views.manage_user",
            "openedx.core.djangoapps.user_api.accounts.utils",
            "openedx.core.djangoapps.user_authn.views.auto_auth",
            "openedx.core.djangoapps.user_authn.views.register",
        ],
        model="generate_password",
        proxy=generate_password
    )


def patch_registration_form_factory():
    """This method patches `RegistrationFormFactory` of user_auth.view.registration_form ,
    with custom nelp `NelpRegistrationFormFactory`.
    """
    # pylint: disable=import-outside-toplevel
    from eox_nelp.edxapp_wrapper.user_authn import views
    from eox_nelp.user_authn.views.registration_form import NelpRegistrationFormFactory
    views.registration_form.RegistrationFormFactory = NelpRegistrationFormFactory


def patch_form_fields_getattr():
    """
    Patches the `form_fields` module within the Open edX user authentication app by dynamically
    injecting a custom `__getattr__` method. This enables on-the-fly resolution of field handlers
    (e.g., `add_<field>_field`) based on runtime configuration, allowing flexible field definition
    without directly modifying the upstream module.
    """
    # pylint: disable=import-outside-toplevel
    from eox_nelp.edxapp_wrapper.user_authn import form_fields
    from eox_nelp.user_authn.api.patches import form_field_getattr_patch
    setattr(form_fields, "__getattr__", form_field_getattr_patch)
