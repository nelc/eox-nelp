"""
This module provides helper functions for managing user-related operations
that extend beyond the default behavior of Open edX account serializers.

It encapsulates logic for updating core user attributes and handling additional
profile information required by specific platform features or customization layers.

These utilities are intended to centralize user update logic, promote reusability,
and maintain clean separation between views and business logic.
"""
from django.conf import settings
from django.utils.translation import gettext as _
from opaque_keys.edx.django.models import CourseKeyField

from eox_nelp.edxapp_wrapper.student import CourseAccessRole
from eox_nelp.edxapp_wrapper.user_api import accounts, errors
from eox_nelp.utils import normalize_national_id, save_extrainfo
from eox_nelp.validators import validate_phone

# Institution-level roles whose holders may not set or change their own national_id.
# A national ID identifies an institution admin to integrations (e.g. delegated MCP
# access), so only staff may put one on such an account. An empty setting disables it.
DEFAULT_NATIONAL_ID_LOCKED_ROLES = ["staff", "instructor", "data_researcher", "org_course_creator_group"]
NATIONAL_ID_LOCKED_MESSAGE = (
    "لا يمكن تعديل رقم الهوية الوطنية ذاتيًا لحسابات أصحاب صلاحيات الجهات، يرجى التواصل مع الدعم. "
    "National ID cannot be changed here for accounts holding institution roles; please contact support."
)


def update_account(user, data):
    """
    Updates core user account fields based on the request data.

    This function:
    - Optionally validates the phone number format if the setting USER_PROFILE_API_VALIDATE_PHONE_NUMBER is True.
    - Calls update_account_settings to update supported fields.
    - Manually updates additional fields (e.g., first_name, last_name) defined in EXTRA_ACCOUNT_USER_FIELDS
      that are not handled by the standard serializers.

    Args:
        user (User): The Django user instance whose data will be updated.
        data (dict): Dictionary containing the fields and values to be updated.

    Raises:
        AccountValidationError: If phone number validation fails.
    """
    validate_phone_number = getattr(settings, 'USER_PROFILE_API_VALIDATE_PHONE_NUMBER', False)
    phone_number = data.get("phone_number")

    if validate_phone_number and phone_number and not validate_phone(phone_number):
        raise errors.AccountValidationError({"phone_number": [_("Invalid phone number")]})

    accounts.api.update_account_settings(user, data)

    # This extra code block is required since the method update_account_settings just
    # allows to update fields defined in the AccountUserSerializer and the AccountLegacyProfileSerializer
    # so some fields like first_name and last_name are not editable in the standad implementation.

    extra_account_user_fields = getattr(settings, "EXTRA_ACCOUNT_USER_FIELDS", [])

    for field in extra_account_user_fields:
        if (value := data.get(field)) and hasattr(user, field):
            setattr(user, field, value)
            user.save()


def update_extrainfo(user, data):
    """
    Updates user-related extra information fields not handled by the standard account serializers.

    This function:
    - Retrieves a list of extra info fields from USER_PROFILE_API_EXTRA_INFO_FIELDS setting.
    - Extracts matching fields from the request data.
    - Persists the data using save_extrainfo helper.

    Fields are saved only if they are present in the request.

    Args:
        user (User): The Django user instance whose extra info will be updated.
        data (dict): Dictionary containing the extra info fields and values to be updated.
    """
    required_user_extra_info_fields = getattr(settings, 'USER_PROFILE_API_EXTRA_INFO_FIELDS', [])
    extra_info_data = {
        field: data[field] for field in required_user_extra_info_fields if field in data
    }

    if extra_info_data:
        check_national_id_lock(user, extra_info_data)
        save_extrainfo(user, extra_info_data)


def holds_institution_role(user):
    """
    Return whether the user holds an institution-level (org-wide, no course) role listed in
    EOX_NELP_NATIONAL_ID_LOCKED_ROLES.

    Args:
        user (User): The Django user instance.

    Returns:
        bool: True when such a role exists, False otherwise or when the setting is empty.
    """
    roles = getattr(settings, "EOX_NELP_NATIONAL_ID_LOCKED_ROLES", DEFAULT_NATIONAL_ID_LOCKED_ROLES)
    if not roles:
        return False

    # Org-level roles store CourseKeyField.Empty; the field refuses None/__isnull lookups.
    return CourseAccessRole.objects.filter(
        user=user,
        course_id=CourseKeyField.Empty,
        role__in=list(roles),
    ).exists()


def check_national_id_lock(user, extra_info_data):
    """
    Refuse a self-service change of national_id for accounts holding an institution role.

    Re-sending the current value is allowed, since profile forms submit every field. Setting it
    for the first time is refused too, so one admin cannot claim another admin's unset ID.

    Args:
        user (User): The Django user instance whose extra info will be updated.
        extra_info_data (dict): The extra info fields about to be saved.

    Raises:
        AccountValidationError: When the national_id would change for such an account.
    """
    if "national_id" not in extra_info_data:
        return

    current = getattr(getattr(user, "extrainfo", None), "national_id", None) or ""
    proposed = extra_info_data["national_id"] or ""

    if normalize_national_id(str(proposed)) == normalize_national_id(str(current)):
        return

    if holds_institution_role(user):
        raise errors.AccountValidationError({"national_id": [NATIONAL_ID_LOCKED_MESSAGE]})
