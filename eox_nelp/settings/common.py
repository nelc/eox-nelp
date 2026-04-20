"""
Settings for eox-core
"""
from __future__ import absolute_import, unicode_literals

from importlib.util import find_spec

SECRET_KEY = 'a-not-to-be-trusted-secret-key'
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.sessions',
    'social_django',
    'eox_nelp',
    'eventtracking.django.apps.EventTrackingConfig',
]

DEFAULT_FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE = (
    "[Futurex platform] Notification due date(left {subsection_delta.days} days) "
    "of subsection {subsection_title} "
    "from course {course_title}"
)
#  APP Labels
COURSE_CREATOR_APP = 'cms.djangoapps.course_creators'
JSON_API_REST_FRAMEWORK = 'rest_framework_json_api'
EOX_AUDIT_MODEL_APP = 'eox_audit_model.apps.EoxAuditModelConfig'
EOX_SUPPORT_APP = 'eox_support.apps.EoxSupportConfig'
CUSTOM_REG_FORM_APP = 'custom_reg_form.apps.CustomRegFormConfig'
LOCALE_PATHS = ["eox_nelp/locale"]


def plugin_settings(settings):
    """
    Defines eox-nelp settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """
    settings.EOX_NELP_COURSE_CREATORS_BACKEND = 'eox_nelp.edxapp_wrapper.backends.course_creators_k_v1'
    settings.EOX_NELP_COURSE_OVERVIEWS_BACKEND = 'eox_nelp.edxapp_wrapper.backends.course_overviews_m_v1'
    settings.EOX_NELP_SITE_CONFIGURATION = 'eox_nelp.edxapp_wrapper.backends.site_configuration_m_v1'
    settings.EOX_NELP_USER_API = 'eox_nelp.edxapp_wrapper.backends.user_api_m_v1'
    settings.EOX_NELP_USER_AUTHN = 'eox_nelp.edxapp_wrapper.backends.user_authn_r_v1'
    settings.EOX_NELP_MFE_CONFIG_VIEW = 'eox_nelp.edxapp_wrapper.backends.mfe_config_view_m_v1'
    settings.EOX_NELP_COURSE_API = 'eox_nelp.edxapp_wrapper.backends.course_api_m_v1'
    settings.EOX_NELP_XMODULE_MODULESTORE = 'eox_nelp.edxapp_wrapper.backends.modulestore_m_v1'
    settings.EOX_NELP_BULK_EMAIL_BACKEND = 'eox_nelp.edxapp_wrapper.backends.bulk_email_m_v1'
    settings.EOX_NELP_STUDENT_BACKEND = 'eox_nelp.edxapp_wrapper.backends.student_m_v1'
    settings.EOX_NELP_EDXMAKO_BACKEND = 'eox_nelp.edxapp_wrapper.backends.edxmako_m_v1'
    settings.EOX_NELP_BRANDING_BACKEND = 'eox_nelp.edxapp_wrapper.backends.branding_m_v1'
    settings.EOX_NELP_CERTIFICATES_BACKEND = 'eox_nelp.edxapp_wrapper.backends.certificates_m_v1'
    settings.EOX_NELP_CMS_API_BACKEND = 'eox_nelp.edxapp_wrapper.backends.cms_api_m_v1'
    settings.EOX_NELP_EVENT_ROUTING_BACKEND = 'eox_nelp.edxapp_wrapper.backends.event_routing_backends_m_v1'
    settings.EOX_NELP_GRADES_BACKEND = 'eox_nelp.edxapp_wrapper.backends.grades_m_v1'
    settings.EOX_NELP_COURSE_BLOCKS_BACKEND = 'eox_nelp.edxapp_wrapper.backends.course_blocks_m_v1'
    settings.EOX_NELP_COURSEWARE_BACKEND = 'eox_nelp.edxapp_wrapper.backends.courseware_m_v1'
    settings.EOX_NELP_INSTRUCTOR_BACKEND = 'eox_nelp.edxapp_wrapper.backends.instructor_m_v1'
    settings.EOX_NELP_COURSE_EXPERIENCE_BACKEND = 'eox_nelp.edxapp_wrapper.backends.course_experience_p_v1'
    settings.EOX_NELP_THIRD_PARTY_AUTH_BACKEND = 'eox_nelp.edxapp_wrapper.backends.third_party_auth_r_v1'
    settings.EOX_NELP_DJANGO_COMMENT_COMMON_BACKEND = 'eox_nelp.edxapp_wrapper.backends.django_comment_common_r_v1'
    settings.EOX_NELP_CONTENTSTORE = 'eox_nelp.edxapp_wrapper.backends.contentstore_r_v1'

    settings.FUTUREX_API_URL = 'https://testing-site.com'
    settings.FUTUREX_API_CLIENT_ID = 'my-test-client-id'
    settings.FUTUREX_API_CLIENT_SECRET = 'my-test-client-secret'
    settings.FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE = DEFAULT_FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE
    settings.BULK_EMAIL_DEFAULT_RETRY_DELAY = 30
    settings.BULK_EMAIL_MAX_RETRIES = 3

    if hasattr(settings, "INSTALLED_APPS") and COURSE_CREATOR_APP not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS.append(COURSE_CREATOR_APP)
    if find_spec(JSON_API_REST_FRAMEWORK) and JSON_API_REST_FRAMEWORK not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS.append(JSON_API_REST_FRAMEWORK)
    if find_spec('eox_audit_model') and EOX_AUDIT_MODEL_APP not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS.append(EOX_AUDIT_MODEL_APP)

    try:
        payments_notifications_context = (
            'eox_nelp.payment_notifications.context_processor.payments_notifications_context'
        )

        if payments_notifications_context not in settings.TEMPLATES[0]['OPTIONS']['context_processors']:
            settings.TEMPLATES[0]['OPTIONS']['context_processors'].append(payments_notifications_context)
        if payments_notifications_context not in settings.TEMPLATES[1]['OPTIONS']['context_processors']:
            settings.TEMPLATES[1]['OPTIONS']['context_processors'].append(payments_notifications_context)

        settings.DEFAULT_TEMPLATE_ENGINE = settings.TEMPLATES[0]
    except AttributeError:
        # We must find a way to register this error
        pass
