"""Middleware file.

Required NELP middlewares that allow to customize edx-platform.

classes:
    ExtendedProfileFieldsMiddleware: Set extended_profile_fields in registration form.
"""
from django.conf import settings
from django.http import Http404, parse_cookie
from django.utils.translation import gettext_lazy as _

from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.edxapp_wrapper.user_api import accounts
from eox_nelp.edxapp_wrapper.user_authn import RegistrationFormFactory

# Copy default values from https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master.nelp
# /openedx/core/djangoapps/user_authn/views/registration_form.py#L308
DEFAULT_EXTRA_FIELDS = [
    "confirm_email",
    "first_name",
    "last_name",
    "city",
    "state",
    "country",
    "gender",
    "year_of_birth",
    "level_of_education",
    "company",
    "job_title",
    "title",
    "mailing_address",
    "goals",
    "honor_code",
    "terms_of_service",
    "profession",
    "specialty",
]


class ExtendedProfileFieldsMiddleware:
    """This middleware class will update the registration form factory extra fields
    based on the tenant setting "extended_profile_fields", therefore the new values will be
    settable from the register form in /register, from /account/settings and finally from
    SAML IDP response.

    Configuration example, add the following in your tenant config:

        extended_profile_fields = [
            "hobby",
            "sport",
            "movie"
        ]

        # if you add this in general setting the default values will be deleted
        REGISTRATION_EXTRA_FIELDS = {
            'hobby': 'required',
            'sport': 'required',
            'movie': 'optional'
        }

        # if you want to add specific options to the  new fields

        EXTRA_FIELD_OPTIONS = {
            'sport': ['soccer', 'football', 'tennis'],
            'movie': ['Harry Potter', 'Karate kid']
        }

        # if you want to add translations

        extended_profile_fields_translations = {
            "ar": {
                'hobby': 'هواية',
            },
            "es": {
                'sport': 'Deporte',
                'movie': 'Pelicula'
            }
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The following line resets to the default values, to avoid tenants overlapping.
        RegistrationFormFactory.EXTRA_FIELDS = DEFAULT_EXTRA_FIELDS.copy()
        extended_profile_fields = configuration_helpers.get_value('extended_profile_fields', [])
        extended_profile_fields_translations = configuration_helpers.get_value(
            'extended_profile_fields_translations',
            {},
        )
        translations = extended_profile_fields_translations.get(request.LANGUAGE_CODE, {})
        extended_profile_fields = list(set(extended_profile_fields) - set(DEFAULT_EXTRA_FIELDS))

        for field_name in extended_profile_fields:
            RegistrationFormFactory.EXTRA_FIELDS.append(field_name)
            setattr(
                RegistrationFormFactory,
                f'_add_{field_name}_field',
                self._generate_handler(field_name, translations.get(field_name, field_name)),
            )
            # Set attributes in accounts since those fields are required by
            # "add_field_with_configurable_select_option" method.
            setattr(
                accounts,
                f'REQUIRED_FIELD_{field_name.upper()}_SELECT_MSG',
                f"{_('Select your')} {translations.get(field_name, field_name)}",
            )
            setattr(
                accounts,
                f'REQUIRED_FIELD_{field_name.upper()}_TEXT_MSG',
                f"{_('Enter your')} {translations.get(field_name, field_name)}",
            )

        return self.get_response(request)

    def _generate_handler(self, field, label):
        """Every field will require a handler method, check the logic here
        https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master.nelp/
        openedx/core/djangoapps/user_authn/views/registration_form.py#L360,
        this method generates a specific handler for each new field with its specific label.

        Args:
            field: String
            label: String
        Returns:
            func: Handler method
        """
        label = label.capitalize()

        def handler(form_instance, form_desc, required=True):
            """Wrapper of https://github.com/eduNEXT/edunext-platform/blob/ednx-release/
            mango.master.nelp/openedx/core/djangoapps/user_authn/views/registration_form.py#L657
            """
            # pylint: disable=protected-access
            form_instance._add_field_with_configurable_select_options(field, label, form_desc, required=required)
        return handler


class TenantExistMiddleware:
    """The value of EDNX_TENANT_DOMAIN is set before starting a request by eox_tenant
    in this line https://github.com/eduNEXT/eox-tenant/blob/master/eox_tenant/signals.py#L52
    if the value doesn't exist that means that there is no TenantRonfig or Route record for
    that specific site. The functionality of this middleware is to block those requests that
    don't have an active tenant configuration
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Check if EDNX_TENANT_DOMAIN has already been set, otherwise raises a 404 error."""
        if hasattr(settings, "EDNX_TENANT_DOMAIN"):
            return self.get_response(request)

        raise Http404


class PreserveUserLanguageCookieMiddleware:
    """This middleware ensure that in the COOKIES property the LANGUAGE_COOKIE_NAME
    key has to be the cookie sent by the user and not other,
    because it could be modified previously by other.
    eg.
    https://github.com/openedx/edx-platform/blob/open-release/palm.master/openedx/
    core/djangoapps/lang_pref/middleware.py#L61-L62
    """
    def process_request(self, request):
        """Process the request to change the language cookie based in original cookie value."""
        original_user_language_cookie = parse_cookie(request.META.get("HTTP_COOKIE", "")).get(
            settings.LANGUAGE_COOKIE_NAME
        )

        if original_user_language_cookie:
            request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = original_user_language_cookie
