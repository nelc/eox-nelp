"""
This module tests the backends of the edxapp_wrapper
"""


# pylint: disable=import-outside-toplevel,unused-import
def test_current_settings_code_imports():
    """
    Running this imports means that our backends import the right signature
    """
    import eox_nelp.edxapp_wrapper.backends.branding_m_v1
    import eox_nelp.edxapp_wrapper.backends.bulk_email_m_v1
    import eox_nelp.edxapp_wrapper.backends.certificates_m_v1
    import eox_nelp.edxapp_wrapper.backends.cms_api_m_v1
    import eox_nelp.edxapp_wrapper.backends.course_api_m_v1
    import eox_nelp.edxapp_wrapper.backends.course_blocks_m_v1
    import eox_nelp.edxapp_wrapper.backends.course_creators_k_v1
    import eox_nelp.edxapp_wrapper.backends.course_experience_p_v1
    import eox_nelp.edxapp_wrapper.backends.course_overviews_m_v1
    import eox_nelp.edxapp_wrapper.backends.courseware_m_v1
    import eox_nelp.edxapp_wrapper.backends.django_comment_common_r_v1
    import eox_nelp.edxapp_wrapper.backends.edxmako_m_v1
    import eox_nelp.edxapp_wrapper.backends.event_routing_backends_m_v1
    import eox_nelp.edxapp_wrapper.backends.grades_m_v1
    import eox_nelp.edxapp_wrapper.backends.instructor_m_v1
    import eox_nelp.edxapp_wrapper.backends.mfe_config_view_m_v1
    import eox_nelp.edxapp_wrapper.backends.modulestore_m_v1
    import eox_nelp.edxapp_wrapper.backends.site_configuration_m_v1
    import eox_nelp.edxapp_wrapper.backends.student_m_v1
    import eox_nelp.edxapp_wrapper.backends.third_party_auth_r_v1
    import eox_nelp.edxapp_wrapper.backends.user_api_m_v1
    import eox_nelp.edxapp_wrapper.backends.user_authn_r_v1  # noqa: F401
