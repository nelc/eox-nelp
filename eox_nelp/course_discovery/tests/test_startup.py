"""Tests for the startup steps of the course discovery override (eox_nelp.init_pipeline)."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches, include, re_path, resolve

from eox_nelp.course_discovery.views import course_discovery
from eox_nelp.edxapp_wrapper.edx_search import search_meilisearch, search_urls, search_views
from eox_nelp.init_pipeline import COURSE_DISCOVERY_ROUTE, make_course_end_filterable, take_over_course_discovery_route

DISCOVERY_URL = "/search/course_discovery/"
urlpatterns = []  # lets this module stand for another app mounted on the same prefix


def mount(*apps):
    """urlconf mounting the given url modules under search/ in the given order."""
    class Conf:  # pylint: disable=too-few-public-methods
        """urlconf holder"""
        urlpatterns = [re_path(r"^search/", include(module)) for module in apps]
    return Conf


class CourseDiscoveryRouteTestCase(SimpleTestCase):
    """edx-search's discovery route runs the eox-nelp view, and drift is loud."""

    def setUp(self):
        self.route = next(r for r in search_urls.urlpatterns if r.name == COURSE_DISCOVERY_ROUTE)
        self.addCleanup(setattr, self.route, "callback", self.route.callback)
        self.route.callback = search_views.course_discovery  # what edx-search builds at import
        self.addCleanup(clear_url_caches)

    def resolved(self, *apps):
        """View function the discovery URL resolves to under an app order."""
        clear_url_caches()
        with override_settings(ROOT_URLCONF=mount(*apps)):
            return resolve(DISCOVERY_URL).func

    def test_takeover_wins_in_both_orders(self):
        """Even when the resolver was built (cached) before the takeover ran.

        Expected behavior:
            - Before: the stock view. After: the eox-nelp view, whatever the order.
        """
        other = __name__
        for apps in ((search_urls, other), (other, search_urls)):
            self.route.callback = search_views.course_discovery
            self.assertIs(self.resolved(*apps), search_views.course_discovery)

            take_over_course_discovery_route()

            with override_settings(ROOT_URLCONF=mount(*apps)):
                self.assertIs(resolve(DISCOVERY_URL).func, course_discovery)

    def test_sibling_routes_keep_their_views(self):
        """The courseware search (do_search) is untouched.

        Expected behavior:
            - /search/ still resolves to the stock view.
        """
        take_over_course_discovery_route()

        with override_settings(ROOT_URLCONF=mount(search_urls)):
            self.assertIs(resolve("/search/").func, search_views.do_search)

    def test_takeover_is_idempotent(self):
        """Safe if ready() runs twice.

        Expected behavior:
            - The callback is the eox-nelp view after two runs.
        """
        take_over_course_discovery_route()
        take_over_course_discovery_route()

        self.assertIs(self.route.callback, course_discovery)

    def test_missing_route_fails_loudly(self):
        """edx-search renaming the route must stop startup, never silently keep the stock view.

        Expected behavior:
            - ImproperlyConfigured naming edx-search.
        """
        self.route.name = "renamed-upstream"
        self.addCleanup(setattr, self.route, "name", COURSE_DISCOVERY_ROUTE)

        with self.assertRaisesRegex(ImproperlyConfigured, "edx-search"):
            take_over_course_discovery_route()


class MakeCourseEndFilterableTestCase(SimpleTestCase):
    """`end` joins the course_info filterable attributes once, and only there."""

    def setUp(self):
        filterables = search_meilisearch.INDEX_FILTERABLES
        self.addCleanup(setattr, search_meilisearch, "INDEX_FILTERABLES", filterables)
        search_meilisearch.INDEX_FILTERABLES = {name: list(fields) for name, fields in filterables.items()}
        for fields in search_meilisearch.INDEX_FILTERABLES.values():
            if "end" in fields:
                fields.remove("end")  # undo the app's ready()

    def test_adds_end_once(self):
        """Idempotent, and the other indexes and attributes are untouched.

        Expected behavior:
            - course_info keeps its attributes and gains `end` exactly once.
            - courseware_content does not change.
        """
        before = {name: list(fields) for name, fields in search_meilisearch.INDEX_FILTERABLES.items()}

        make_course_end_filterable()
        make_course_end_filterable()

        self.assertEqual(search_meilisearch.INDEX_FILTERABLES["course_info"], before["course_info"] + ["end"])
        self.assertEqual(search_meilisearch.INDEX_FILTERABLES["courseware_content"], before["courseware_content"])

    @override_settings(COURSEWARE_INFO_INDEX_NAME="catalog")
    def test_unknown_index_fails_loudly(self):
        """edx-search keys INDEX_FILTERABLES by the same setting; a mismatch means upstream changed.

        Expected behavior:
            - ImproperlyConfigured naming the index.
        """
        with self.assertRaisesRegex(ImproperlyConfigured, "catalog"):
            make_course_end_filterable()
