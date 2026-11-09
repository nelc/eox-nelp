"""Backend test abstraction."""
from mock import Mock


def get_lti_ags_score_model():
    """Test backend for eox_nelp.edxapp_wrapper.backends.lti_consumer_t_v1.

    Returns:
        Mock class.
    """
    return Mock()


get_user_from_external_user_id = Mock()
