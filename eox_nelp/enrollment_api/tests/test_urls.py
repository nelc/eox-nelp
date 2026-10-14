"""Contract tests for the URL takeover (decision a2-url-takeover)."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches, include, re_path, resolve
from eox_core.api.v1 import urls as core_urls
from eox_core.api.v1.views import EdxappEnrollment as CoreEdxappEnrollment

from eox_nelp.enrollment_api.views import NelpEdxappEnrollment
from eox_nelp.init_pipeline import CORE_ENROLLMENT_ROUTE, take_over_core_enrollment_route

ENROLLMENT_URL = "/eox-core/api/v1/enrollment/"
CORE = (r"^eox-core/api/v1/", "eox_core.api.v1.urls")
# Another plugin mounted on the same prefix, standing in for "whatever else stevedore yields".
OTHER = (r"^eox-core/api/v1/other/", "eox_nelp.enrollment_api.tests.test_urls")
urlpatterns = []  # lets OTHER be includable


def mount(*apps):
    """urlconf mounting plugin url_configs in the given order (eox-core's full urls.py needs edx-proctoring)."""
    class Conf:  # pylint: disable=too-few-public-methods
        """urlconf holder"""
        urlpatterns = [re_path(regex, include(path)) for regex, path in apps]
    return Conf


class UrlTakeoverTestCase(SimpleTestCase):
    """The eox-core route runs the eox-nelp view whatever the plugin order, and drift is loud."""

    def setUp(self):
        self.route = next(r for r in core_urls.urlpatterns if r.name == CORE_ENROLLMENT_ROUTE)
        self.original = self.route.callback  # already swapped if the app's ready() ran in this process
        self.addCleanup(setattr, self.route, "callback", self.original)
        self.core_callback = CoreEdxappEnrollment.as_view()  # what eox-core itself builds at import
        self.route.callback = self.core_callback
        self.addCleanup(clear_url_caches)

    def resolved_view(self, *apps):
        """View class the enrollment URL resolves to under a plugin order."""
        clear_url_caches()
        with override_settings(ROOT_URLCONF=mount(*apps)):
            return resolve(ENROLLMENT_URL).func.view_class

    def test_without_takeover_eox_core_serves_the_url(self):
        """Why the takeover exists (eox-core's own route is built from its view)."""
        self.assertIsNot(self.resolved_view(CORE), NelpEdxappEnrollment)

    def test_takeover_wins_in_both_plugin_orders(self):
        """Even when the resolver was already built (cached) before the takeover ran."""
        for apps in ((CORE, OTHER), (OTHER, CORE)):
            self.route.callback = self.core_callback
            self.resolved_view(*apps)  # warm the resolver cache
            take_over_core_enrollment_route()
            with override_settings(ROOT_URLCONF=mount(*apps)):
                self.assertIs(resolve(ENROLLMENT_URL).func.view_class, NelpEdxappEnrollment)

    def test_only_the_enrollment_route_is_taken(self):
        """Sibling eox-core routes keep their own views."""
        take_over_core_enrollment_route()
        with override_settings(ROOT_URLCONF=mount(CORE)):
            for path in ("/eox-core/api/v1/pre-enrollment/", "/eox-core/api/v1/user/"):
                self.assertIsNot(resolve(path).func.view_class, NelpEdxappEnrollment)

    def test_takeover_is_idempotent(self):
        """Safe if ready() runs twice."""
        take_over_core_enrollment_route()
        take_over_core_enrollment_route()
        self.assertIs(self.route.callback.view_class, NelpEdxappEnrollment)

    def test_missing_route_fails_loudly(self):
        """eox-core renaming the route must stop startup, never silently keep its view."""
        self.route.name = "renamed-upstream"
        self.addCleanup(setattr, self.route, "name", CORE_ENROLLMENT_ROUTE)
        with self.assertRaises(ImproperlyConfigured):
            take_over_core_enrollment_route()
