"""
Settings for eox-nelp
"""

import os
from pathlib import Path

from .common import *  # pylint: disable=wildcard-import, unused-wildcard-import  # noqa: F401

BASE_DIR = Path(__file__).resolve().parent.parent


class SettingsClass:
    """ dummy settings class """


def test_plugin_settings(settings):
    """
    Defines eox-nelp settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """
    settings.EOX_NELP_COURSE_CREATORS_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.course_creators_k_v1'
    settings.EOX_NELP_COURSE_OVERVIEWS_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.course_overviews_m_v1'
    settings.EOX_NELP_SITE_CONFIGURATION = 'eox_nelp.edxapp_wrapper.test_backends.site_configuration_m_v1'
    settings.EOX_NELP_USER_API = 'eox_nelp.edxapp_wrapper.test_backends.user_api_m_v1'
    settings.EOX_NELP_USER_AUTHN = 'eox_nelp.edxapp_wrapper.test_backends.user_authn_r_v1'
    settings.EOX_NELP_MFE_CONFIG_VIEW = 'eox_nelp.edxapp_wrapper.test_backends.mfe_config_view_m_v1'
    settings.EOX_NELP_COURSE_API = 'eox_nelp.edxapp_wrapper.test_backends.course_api_m_v1'
    settings.EOX_NELP_XMODULE_MODULESTORE = 'eox_nelp.edxapp_wrapper.test_backends.modulestore_m_v1'
    settings.EOX_NELP_BULK_EMAIL_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.bulk_email_m_v1'
    settings.EOX_NELP_STUDENT_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.student_m_v1'
    settings.EOX_NELP_EDXMAKO_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.edxmako_m_v1'
    settings.EOX_NELP_BRANDING_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.branding_m_v1'
    settings.EOX_NELP_CERTIFICATES_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.certificates_m_v1'
    settings.EOX_NELP_CMS_API_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.cms_api_m_v1'
    settings.EOX_NELP_EVENT_ROUTING_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.event_routing_backends_m_v1'
    settings.EOX_NELP_GRADES_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.grades_m_v1'
    settings.EOX_NELP_COURSE_BLOCKS_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.course_blocks_m_v1'
    settings.EOX_NELP_COURSEWARE_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.courseware_m_v1"
    settings.EOX_NELP_INSTRUCTOR_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.instructor_m_v1"
    settings.EOX_NELP_COURSE_EXPERIENCE_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.course_experience_p_v1"
    settings.EOX_NELP_THIRD_PARTY_AUTH_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.third_party_auth_r_v1"
    settings.EOX_NELP_DJANGO_COMMENT_COMMON_BACKEND = 'eox_nelp.edxapp_wrapper.test_backends.django_comment_common_r_v1'
    settings.EOX_NELP_CONTENTSTORE = 'eox_nelp.edxapp_wrapper.test_backends.contentstore_r_v1'

    settings.FUTUREX_API_URL = 'https://testing.com'
    settings.FUTUREX_API_CLIENT_ID = 'my-test-client-id'
    settings.FUTUREX_API_CLIENT_SECRET = 'my-test-client-secret'
    settings.FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE = DEFAULT_FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE  # noqa: F405
    settings.EXTERNAL_CERTIFICATES_API_URL = 'https://testing.com'
    settings.EXTERNAL_CERTIFICATES_USER = 'test-user'
    settings.EXTERNAL_CERTIFICATES_PASSWORD = 'test-password'
    settings.MINISTER_OF_TOURISM_API_URL = 'https://testing.com'
    settings.MINISTER_OF_TOURISM_USER = 'test-user'
    settings.MINISTER_OF_TOURISM_PASSWORD = 'test-password'
    settings.ENABLE_CERTIFICATE_PUBLISHER = True
    settings.SMS_VENDOR_URL = 'https://testing.com'
    settings.SMS_VENDOR_USERNAME = 'test-user'
    settings.SMS_VENDOR_PASSWORD = 'test-password'
    settings.SMS_VENDOR_TOKEN_PATH = "oauth2/v1/token"
    settings.SMS_VENDOR_SEND_SMS_PATH = 'sms/send'

    settings.PEARSON_RTI_WSDL_URL = 'https://testing.com'
    settings.PEARSON_RTI_CERT = '/openedx/certs/cert.p12'
    settings.PEARSON_RTI_PASSPHRASE = 'test-password'
    settings.PEARSON_RTI_WSDL_USERNAME = "testing"
    settings.PEARSON_RTI_WSDL_PASSWORD = "12345678p"
    settings.PEARSON_RTI_WSDL_CLIENT_ID = "12345678"

    settings.PEARSON_ENGINE_API_URL = 'https://testing.com'
    settings.PEARSON_ENGINE_API_CLIENT_SECRET = "12345678p"
    settings.PEARSON_ENGINE_API_CLIENT_ID = "12345678"


PLATFORM_NAME = "Testing environment"

SETTINGS = SettingsClass()
test_plugin_settings(SETTINGS)
vars().update(SETTINGS.__dict__)


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3',
    }
}

ALLOWED_HOSTS = ['*']
ENV_ROOT = '.'
ROOT_URLCONF = 'eox_nelp.urls'

FEATURES = {
    'ENABLE_OTHER_COURSE_SETTINGS': True,
}

COURSE_KEY_PATTERN = r'(?P<course_key_string>[^/+]+(/|\+)[^/+]+(/|\+)[^/?]+)'
COURSE_ID_PATTERN = COURSE_KEY_PATTERN.replace('course_key_string', 'course_id')

USERNAME_REGEX_PARTIAL = r'[\w .@_+-]+'
USERNAME_PATTERN = fr'(?P<username>{USERNAME_REGEX_PARTIAL})'

SILENCED_SYSTEM_CHECKS = [
    'admin.E403', 'admin.E406', 'admin.E408', 'admin.E409', 'admin.E410', 'admin.E002', 'admin.E035',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
TESTING_MIGRATIONS = True

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'edx_rest_framework_extensions.paginators.DefaultPagination',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'PAGE_SIZE': 10,
    'URL_FORMAT_OVERRIDE': None,
    'DEFAULT_THROTTLE_RATES': {
        'user': '60/minute',
        'service_user': '800/minute',
        'registration_validation': '30/minute',
    },
}
EVENT_TRACKING_ENABLED = True
PEARSON_RTEN_API_WRITE_ENABLED = True
PEARSON_RTEN_API_READ_ENABLED = True

# ------------external plugins configuration backends----------------

EOX_THEMING_CONFIGURATION_HELPER_BACKEND = 'eox_theming.edxapp_wrapper.backends.j_configuration_helpers_tests'
EOX_THEMING_THEMING_HELPER_BACKEND = 'eox_theming.edxapp_wrapper.backends.j_theming_helpers_tests'
EOX_THEMING_EDXMAKO_BACKEND = 'eox_theming.edxapp_wrapper.backends.j_mako_tests'
EOX_THEMING_BASE_LOADER_BACKEND = 'eox_theming.edxapp_wrapper.backends.j_loaders_tests'
EOX_THEMING_CONFIG_SOURCES = [
    'from_django_settings',
]

EOX_CORE_COURSEWARE_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.courseware_m_v1"
EOX_CORE_GRADES_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.grades_m_v1"
EOX_CORE_CERTIFICATES_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.certificates_m_v1"
EOX_CORE_USERS_BACKEND = "eox_nelp.edxapp_wrapper.test_backends.users_p_v1"
EOX_CORE_BEARER_AUTHENTICATION = 'eox_core.edxapp_wrapper.backends.bearer_authentication_j_v1_test'
EOX_CORE_LOAD_PERMISSIONS = False

GET_SITE_CONFIGURATION_MODULE = 'eox_tenant.edxapp_wrapper.backends.site_configuration_module_test_v1'
GET_THEMING_HELPERS = 'eox_tenant.edxapp_wrapper.backends.theming_helpers_test_v1'
EOX_TENANT_USERS_BACKEND = 'eox_tenant.edxapp_wrapper.backends.users_test_v1'

# ------------eox-audit external config for tests------------------------------
if find_spec('eox_audit_model') and EOX_AUDIT_MODEL_APP not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.append(EOX_AUDIT_MODEL_APP)  # noqa: F405

# ------------custom reg form config for tests------------------------------
if CUSTOM_REG_FORM_APP not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.append(CUSTOM_REG_FORM_APP)  # noqa: F405

ALLOW_EOX_AUDIT_MODEL = False
CELERY_TASK_ALWAYS_EAGER = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'static'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'debug': True,
        },
    },
]

# ------------user profile api settings------------------------------
USER_PROFILE_API_VALIDATE_PHONE_NUMBER = True
