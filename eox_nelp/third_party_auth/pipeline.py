"""Custom NELP  authentication pipelines

functions:
    social_details: Allows to map response fields to user standard fields.
    invalidate_current_user: Sets to None the current user.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from social_core.pipeline.social_auth import associate_user
from social_core.pipeline.social_auth import social_details as social_core_details

from eox_nelp.edxapp_wrapper.edxmako import edxmako
from eox_nelp.edxapp_wrapper.third_party_auth import Registry
from eox_nelp.edxapp_wrapper.user_authn import get_registration_extension_form
from eox_nelp.third_party_auth.utils import get_value_from_nested_dict, match_user_using_uid_query

logger = logging.getLogger(__name__)
User = get_user_model()


def social_details(backend, details, response, *args, **kwargs):
    """This is an extension of `social_core.pipeline.social_auth.social_details` that allows
    to map response fields in standard user fields. This depends on the SOCIAL_DETAILS_MAPPING
    setting that should be configured as the following:

    Example:

        SOCIAL_DETAILS_MAPPING = {
            "username": "custom_username_response_value",
            "email": "custom_email_response_value",
            "first_name": "custom_first_name_response_value",
            "last_name": "custom_last_name_response_value",
            "fullname": "custom_fullname_response_value"
        }
    """
    details = social_core_details(backend, details, response, *args, **kwargs)

    for key, value in getattr(settings, "SOCIAL_DETAILS_MAPPING", {}).items():
        details["details"][key] = response.get(value)

    return details


def invalidate_current_user(*args, user=None, **kwargs):  # pylint: disable=unused-argument
    """This pipeline sets to None the current user in order to avoid invalid associations.

    This was implemented due to an unexpected behavior when a user is logged and a different
    user tries to authenticate by using a SAML IDP in the same browser, the result is that
    instead of having two different accounts the second user is associated to the first user's
    account, this behavior is the result of SESSION_COOKIE_SAMESITE = "None" however the
    possible fix, SESSION_COOKIE_SAMESITE = "Lax", has not been tested in the whole platform
    therefore that can not be implemented yet.

    **NOTE**
        * This MUST be the first pipeline.
        * This just has been tested in the NELP environment where the linked accounts feature
         was deactivated.
    """
    if user:
        return {
            "user": None
        }

    return {}


def close_mismatch_session(request, *args, user=None, **kwargs):  # pylint: disable=unused-argument
    """This pipeline closes the current session if the pipeline user doesn't match with the session user.

    This ensures that the browser session will show the right account, when a user tries to authenticate
    in a device that has a logged account.
    """
    if request.user != user:
        logout(request)

    return {}


def safer_associate_user_by_national_id(  # pylint: disable=unused-argument
    request, backend, details, response, *args, user=None, **kwargs,
):
    """Pipeline to retrieve user if possible matching uid with the user.extrainfo.national_id records if possible.

    Returns:
        dict: Dict with user if matches once, if match multiple or not match return None.
    """
    if user:
        return None

    user_match = match_user_using_uid_query(backend, response, user_query="extrainfo__national_id")

    if not user_match:
        return None

    return {
        "user": user_match,
        "is_new": False,
    }


def safer_associate_user_by_social_auth_record(  # pylint: disable=unused-argument
    request, backend, details, response, *args, user=None, **kwargs,
):
    """Pipeline to retrieve user if possible matching uid with the if endswith with user.social_auth.uid
    records if possible.
    Returns:
        dict: Dict with user if matches once, if match multiple or not match return None.
    """
    if user:
        return None

    user_match = match_user_using_uid_query(backend, response, user_query="social_auth__uid__endswith")

    if not user_match:
        return None

    return {
        "user": user_match,
        "is_new": False,
    }


def disallow_staff_superuser_users(  # pylint: disable=unused-argument
    request, backend, details, response, *args, user=None, **kwargs,
):
    """Pipeline that forbids staff or superusers

    Return:
        HttpResponseForbidden: If someone tries to have staff or superuser permission using tpa.
    """
    if not user:
        return None

    if user.is_staff or user.is_superuser:
        return HttpResponseForbidden(
            edxmako.shortcuts.render_to_string(
                "static_templates/server-error.html",
                {
                    "page_header": _("It is not allowed to auto associate staff or admin users"),
                    "page_content": _(
                        "You are trying to access with a user that already exists with privileged permissions."
                        " Please try to authenticate on the site where you registered for the first time "
                        "or contact support to change permissions."
                    ),
                },
                request=request,
            )
        )
    return {}


def validate_national_id_and_associate_user(request, backend, uid, *args, user=None, social=None, **kwargs):
    """
    Validates the user's national ID against the provided SAML UID before associating
    a SAML identity with a Django user. If validation fails, the session is ended, and
    the user is redirected to registration.

    Args:
        request (HttpRequest): The HTTP request object.
        backend: The authentication backend used, such as SAML.
        uid (str): Unique identifier from SAML (e.g., user ID).
        user (User, optional): Django user instance, if found.
        social (optional): Existing social authentication data, if found.

    Returns:
        If the UID validation succeeds, proceeds to associate the user with social auth.
        Otherwise, logs out the current session and redirects to the registration page.
    """
    national_id = user.extrainfo.national_id if user and hasattr(user, "extrainfo") else ""

    if national_id and uid.endswith(national_id):
        return associate_user(backend, uid, user, social, *args, **kwargs)

    logger.warning(
        "User association failed: UID does not end with the user's national ID. UID: %s, National ID: %s",
        uid,
        national_id,
    )
    logout(request)

    return redirect("/register")


def custom_form_force_sync(strategy, details, *args, user=None, **kwargs):  # pylint: disable=unused-argument
    """
    Synchronizes custom form data with the learner profile if the provider supports data synchronization.

    This function retrieves the registration extension form and attempts to update or create
    a corresponding model instance using the provided user and details. If multiple instances
    are found, an error is logged.

    Args:
        strategy: The strategy used in the pipeline, containing context and request data.
        details (dict): The data to synchronize with the custom form model.
        user (User, optional): The user associated with the custom form synchronization. Defaults to None.
        *args: Additional arguments passed to the function.
        **kwargs: Additional keyword arguments passed to the function.

    Raises:
        None explicitly, but logs an error if multiple objects are returned during synchronization.

    Expected behavior:
        - Retrieves the current provider from the pipeline using the strategy's backend name.
        - If the user, custom form, and provider are valid, and the provider supports learner profile
          data synchronization:
            - Updates or creates an instance of the custom form model with the provided user and details.
            - Logs an error if multiple objects are returned during the operation.
    """
    current_provider = Registry.get_from_pipeline({'backend': strategy.request.backend.name, 'kwargs': kwargs})
    custom_form = get_registration_extension_form()

    if user and custom_form and current_provider and current_provider.sync_learner_profile_data:
        try:
            custom_form_model = custom_form.Meta.model
            defaults = {key: value for key, value in details.items() if key in custom_form.fields.keys()}

            obj, created = custom_form_model.objects.update_or_create(
                user=user,
                defaults=defaults,
            )
            action = "created" if created else "updated"
            logger.info("Custom form object with id %s has been successfully %s", obj.id, action)
        except MultipleObjectsReturned:
            logger.error("Invalid custom form synchronization, multiple objects returned, for user with id %s", user.id)


def safer_associate_user_by_attribute(backend, response, *args, user=None, **kwargs):  # pylint: disable=unused-argument
    """
    Pipeline step for authentication backends.

    Purpose:
        Allow automatic user association by extracting a value from a deeply nested
        attribute inside the IdP response JSON and using it to identify an existing
        local user through a configurable Django ORM lookup.

    Configuration:
        Each backend can declare a mapping in settings such as:

        SOCIAL_AUTH_<BACKEND_NAME>_USER_ASSOCIATION_ATTRIBUTE = {
            "attribute_path": "user.details.profile.information.national_id",
            "user_query": "extrainfo__national_id",
        }

        Where:
        - `attribute_path` is a dot-separated path used to locate the value inside
          the IdP JSON response (supports nested dictionaries).
        - `user_query` is the Django ORM lookup used to search for the user in the
          local database.

    Behavior:
        - If the extracted value exists and exactly one user matches the query,
          the pipeline returns {"user": matched_user, "is_new": False}.
        - If no value is found, no user matches, or multiple matches exist, the
          pipeline safely returns None to avoid incorrect associations.

    Returns:
        dict: {"user": User, "is_new": False} if a single match is found.
        None: if no secure and deterministic match can be made.
    """
    if user:
        return None

    backend_name_upper = backend.name.replace("-", "_").upper()
    setting_name = f"SOCIAL_AUTH_{backend_name_upper}_USER_ASSOCIATION_ATTRIBUTE"
    match_config = getattr(settings, setting_name, {})
    attribute_path = match_config.get("attribute_path")
    user_query = match_config.get("user_query")

    if not attribute_path or not user_query:
        return None

    # Extract value from IdP JSON response (nested)
    lookup_value = get_value_from_nested_dict(response, attribute_path)

    if lookup_value is None:
        return None

    # Perform lookup in the user model
    try:
        matched_user = User.objects.get(**{user_query: lookup_value})
    except ObjectDoesNotExist:
        # No matching user; let the rest of the pipeline continue normally.
        return None
    except MultipleObjectsReturned:
        # Ambiguous match; safer to do nothing than to pick the wrong account.
        return None

    return {
        "user": matched_user,
        "is_new": False,
    }
