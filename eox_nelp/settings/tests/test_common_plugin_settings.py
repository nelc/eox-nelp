"""This file contains test for the `plugin_settings` method of
common setting of eox-nelp.

Classes:
    CommonPluginSettingsTestCase: Test `plugin_settings` method.

"""
import unittest

from eox_nelp.settings.common import COURSE_CREATOR_APP, plugin_settings


class SettingsClass:
    """ dummy settings class """


class CommonPluginSettingsTestCase(unittest.TestCase):
    """Test class for function `plugin_settings`"""

    def test_base_common_plugin_settings(self):
        """Test when `plugin_settings` is called
        with the required parameters. Check the functions inside are called with
        their desired values.

        Expected behavior:
            - Eox-nelp setting items are presented.
        """
        common_settings = SettingsClass()
        eox_nelp_config = {
            "EOX_NELP_COURSE_CREATORS_BACKEND": "eox_nelp.edxapp_wrapper.backends.course_creators_k_v1",
            "EOX_NELP_COURSE_OVERVIEWS_BACKEND": "eox_nelp.edxapp_wrapper.backends.course_overviews_m_v1",
            "EOX_NELP_SITE_CONFIGURATION": "eox_nelp.edxapp_wrapper.backends.site_configuration_m_v1",
            "EOX_NELP_USER_API": "eox_nelp.edxapp_wrapper.backends.user_api_m_v1",
            "EOX_NELP_USER_AUTHN": "eox_nelp.edxapp_wrapper.backends.user_authn_m_v1",
            "EOX_NELP_MFE_CONFIG_VIEW": "eox_nelp.edxapp_wrapper.backends.mfe_config_view_m_v1",
            "EOX_NELP_COURSE_API": "eox_nelp.edxapp_wrapper.backends.course_api_m_v1",
            "FUTUREX_API_URL": "https://testing-site.com",
            "FUTUREX_API_CLIENT_ID": "my-test-client-id",
            "FUTUREX_API_CLIENT_SECRET": "my-test-client-secret",
        }

        plugin_settings(common_settings)

        assert eox_nelp_config.items() <= common_settings.__dict__.items()

    def test_append_course_creator_app(self):
        """Test when `plugin_settings` is called
        append the course_creator apps in INSTALLED APPS.

        Expected behavior:
            - Course creator app is presentend in INSTALLED_APPS.
        """
        common_settings = SettingsClass()
        setattr(common_settings, "INSTALLED_APPS", [])

        plugin_settings(common_settings)

        self.assertIn(COURSE_CREATOR_APP, getattr(common_settings, "INSTALLED_APPS"))
