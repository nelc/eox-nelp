"""Contract tests for the URL takeover (decision a2-url-takeover)."""
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches, include, re_path, resolve

from eox_nelp.enrollment_api.apps import EnrollmentApiConfig
from eox_nelp.enrollment_api.views import NelpEdxappEnrollment

ENROLLMENT_URL = "/eox-core/api/v1/enrollment/"
URL_CONFIG = EnrollmentApiConfig.plugin_app["url_config"]["lms.djangoapp"]


def mount(*apps):
    """Build a urlconf module-like object mounting plugin url_configs in the given order."""
    class Conf:  # pylint: disable=too-few-public-methods
        """urlconf holder"""
        urlpatterns = [re_path(regex, include(path)) for regex, path in apps]
    return Conf


# eox-core's api/v1 routes (its full urls.py needs edx-proctoring, absent from the unit environment)
CORE = (r"^eox-core/api/v1/", "eox_core.api.v1.urls")
NELP = (URL_CONFIG["regex"], "eox_nelp.enrollment_api.urls")


class UrlTakeoverTestCase(SimpleTestCase):
    """What the plugin route does, and the order dependency the image test guards."""

    def resolve_with(self, *apps):
        """Resolve the enrollment URL under a plugin order."""
        clear_url_caches()
        with override_settings(ROOT_URLCONF=mount(*apps)):
            return resolve(ENROLLMENT_URL).func.view_class

    def test_plugin_route_serves_the_eox_nelp_view_when_it_is_mounted_first(self):
        """Same URL, our view."""
        self.assertIs(self.resolve_with(NELP, CORE), NelpEdxappEnrollment)

    def test_core_route_wins_when_it_is_mounted_first(self):
        """Why the built-image test is mandatory: plugin order decides, and it is not a contract."""
        self.assertIsNot(self.resolve_with(CORE, NELP), NelpEdxappEnrollment)

    def test_only_the_exact_enrollment_url_is_taken(self):
        """Other eox-core routes (pre-enrollment, user, enrollment/x) are not shadowed."""
        clear_url_caches()
        with override_settings(ROOT_URLCONF=mount(NELP, CORE)):
            for path in ("/eox-core/api/v1/pre-enrollment/", "/eox-core/api/v1/user/"):
                self.assertIsNot(resolve(path).func.view_class, NelpEdxappEnrollment)

    def test_plugin_declaration(self):
        """Own label and namespace; lms only."""
        self.assertEqual(EnrollmentApiConfig.label, "eox_nelp_enrollment_api")
        self.assertEqual(URL_CONFIG["namespace"], "eox-nelp-enrollment-api")
        self.assertNotIn("cms.djangoapp", EnrollmentApiConfig.plugin_app["url_config"])
