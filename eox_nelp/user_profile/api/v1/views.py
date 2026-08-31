"""
Views for the NELP user profile application.

This module provides API endpoints for managing and validating user profile data, including updating user information
and retrieving validation errors for required fields.

Available Views:
  - update_user_data: Updates user profile fields, handling extra account and extra info fields where necessary.
  - get_validated_user_fields: Returns a JSON response with validated user fields based on validation rules
    defined in the REQUIRED_USER_FIELDS setting.
"""
import logging

from django.conf import settings
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from eox_nelp.edxapp_wrapper.user_api import errors
from eox_nelp.one_time_password.view_decorators import validate_otp
from eox_nelp.pearson_vue_engine.tasks import real_time_import_task_v2
from eox_nelp.user_profile.api.v1.helpers import update_account, update_extrainfo
from eox_nelp.user_profile.required_fields_validation import validate_required_user_fields

logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes((
    SessionAuthenticationAllowInactiveUser,
))
@permission_classes((IsAuthenticated,))
@validate_otp
def update_user_data(request):
    """ View to update user's fields.
    ## Usage

    ### **POST** /eox-nelp/api/user-profile/v1/update-user-data/

    request example data:
    ``` json
    {
        "phone_number": 3213123123,
        "one_time_password": "234fasds"
    }
    ```
    **POST Response Values**
    ``` json
    {
        "message": "User's fields has been updated successfully"
    }
    ```
    """
    try:
        user = request.user
        data = request.data
        update_account(user, data)
        update_extrainfo(user, data)
    except errors.AccountValidationError as err:
        return Response({"field_errors": err.field_errors}, status=status.HTTP_400_BAD_REQUEST)
    except errors.AccountUpdateError as err:
        return Response(
            {
                "developer_message": err.developer_message,
                "user_message": err.user_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    if (
        getattr(settings, "USE_PEARSON_ENGINE_SERVICE", False)
        and getattr(settings, "PEARSON_ENGINE_UPDATE_USER_PROFILE_ENABLED", True)
    ):
        real_time_import_task_v2.delay(
            user_id=request.user.id,
            action_name="cdd",
        )

    return Response({"message": "User's fields has been updated successfully"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes((SessionAuthenticationAllowInactiveUser,))
@permission_classes((IsAuthenticated,))
def get_validated_user_fields(request):
    """
    View to retrieve validated fields for the authenticated user in JSON format.

    ## Usage

    ### **GET** /eox-nelp/api/user-profile/v1/validated-fields/

    **Response Example**
    ```json
    {
        "account": {
            "first_name": [],
            "last_name": []
        },
        "profile": {
            "city": [],
            "country": [],
            "phone_number": ["Empty field"],
            "mailing_address": []
        },
        "extra_info": {
            "arabic_name": [],
            "arabic_first_name": [],
            "arabic_last_name": []
        }
    }
    ```
    """
    validated_fields = validate_required_user_fields(request.user)

    return Response(validated_fields, status=status.HTTP_200_OK)
