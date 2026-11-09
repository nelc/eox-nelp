"""Backend for the xblock-lti-consumer app.
This file contains all the necessary lti_consumer dependencies from
https://github.com/openedx/xblock-lti-consumer/tree/master/lti_consumer
"""
from lti_consumer.exceptions import LtiError  # pylint: disable=import-error
from lti_consumer.models import LtiAgsScore  # pylint: disable=import-error
from lti_consumer.plugin.compat import get_user_from_external_user_id as _get_user  # pylint: disable=import-error


def get_lti_ags_score_model():
    """Allow to get the LtiAgsScore model.

    Returns:
        LtiAgsScore model.
    """
    return LtiAgsScore


def get_user_from_external_user_id(external_user_id):
    """User of an LTI external user id (the `sub` the tool echoes back).

    Args:
        external_user_id (str): External user id of type `lti`.

    Returns:
        User or None when the id is unknown or malformed.
    """
    try:
        return _get_user(external_user_id)
    except LtiError:
        return None
