"""Utils module to dont repeat code."""
import logging
import operator
from functools import reduce

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned

from eox_nelp.utils import is_valid_national_id_check_digit, normalize_national_id

logger = logging.getLogger(__name__)


def match_user_using_uid_query(backend, response, user_query):
    """Look up for a user using query to match uid.
    The uid is based in the configuration of the saml with the field `attr_user_permanent_id`:
    https://github.com/python-social-auth/social-core/blob/master/social_core/backends/saml.py#L49

    This is using the idp and the uid inspired in:
    https://github.com/python-social-auth/social-core/blob/master/social_core/backends/saml.py#L296C23-L297
    Args:
        backend (backend): backend to use strategy to get user model
        response (dict): Response Dict
        user_query (str): string query to find the user.
    Returns:
        user_match(User): User matched object or None
    """
    user_match = None
    idp = backend.get_idp(response["idp_name"])
    uid = idp.get_user_permanent_id(response["attributes"])
    try:
        user_match = backend.strategy.storage.user.get_user(**{user_query: uid})
    except MultipleObjectsReturned as exc:
        logger.info(
            "Pipeline tries to match user with uid(%s) using %s, but Multiple users found: %s",
            uid,
            user_query,
            str(exc),
        )

    return user_match


def get_value_from_nested_dict(data, path):
    """
    Extract a nested field from a JSON-like dict using dot notation.
    Example:
        data = {"user": {"details": {"profile": {"information": {"national_id": 123}}}}}
        path = "user.details.profile.information.national_id"
        → returns 123
    """
    try:
        keys = path.split(".")
        return reduce(operator.getitem, keys, data)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def get_national_id_claim(backend, response):
    """Return the national ID the identity provider asserts, normalized, or an empty string.

    The claim is located with the `attribute_path` of the backend setting
    SOCIAL_AUTH_<BACKEND_NAME>_USER_ASSOCIATION_ATTRIBUTE, e.g. for the MT provider:

        SOCIAL_AUTH_CONFIG_BASED_OPENIDCONNECT_PKCE_USER_ASSOCIATION_ATTRIBUTE = {
            "attribute_path": "client_NationalId",
            "user_query": "extrainfo__national_id",
        }

    Arabic-Indic digits are translated to ASCII. A value without a valid shape and check digit is
    treated as absent, so it can never match or overwrite an account.

    Args:
        backend (backend): The social auth backend running the pipeline.
        response (dict): The identity provider response.

    Returns:
        str: The normalized national ID, or an empty string when it is missing or invalid.
    """
    backend_name_upper = backend.name.replace("-", "_").upper()
    match_config = getattr(settings, f"SOCIAL_AUTH_{backend_name_upper}_USER_ASSOCIATION_ATTRIBUTE", None) or {}
    attribute_path = match_config.get("attribute_path")

    if not attribute_path:
        return ""

    value = get_value_from_nested_dict(response, attribute_path)

    if value is None:
        return ""

    national_id = normalize_national_id(str(value))

    if not is_valid_national_id_check_digit(national_id):
        logger.warning("The national ID claim sent by the identity provider is invalid and was ignored.")
        return ""

    return national_id
