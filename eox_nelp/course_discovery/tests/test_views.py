"""Tests for eox_nelp.course_discovery.views."""
from unittest.mock import call, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from eox_nelp.course_discovery.views import course_discovery

URL = "/search/course_discovery/"
VIEWS = "eox_nelp.course_discovery.views"


class CourseDiscoveryViewTestCase(SimpleTestCase):
    """The view behaves as edx-search's `course_discovery` but runs the eox-nelp search."""

    def setUp(self):
        self.factory = RequestFactory()
        search = patch(f"{VIEWS}.course_discovery_search", return_value={"total": 3, "results": []})
        track = patch(f"{VIEWS}.track")
        self.search = search.start()
        self.track = track.start()
        self.addCleanup(search.stop)
        self.addCleanup(track.stop)

    def post(self, data):
        """POST to the view as an anonymous user."""
        request = self.factory.post(URL, data)
        request.user = AnonymousUser()
        return course_discovery(request)

    def test_searches_with_the_eox_nelp_search(self):
        """Paging and supported fields reach the eox-nelp search; unsupported fields are dropped.

        Expected behavior:
            - Status 200 with the search results.
            - The search gets the term, size, offset and only the discovery filter fields.
            - Both upstream tracking events are emitted.
        """
        response = self.post({
            "search_string": "data", "page_size": "10", "page_index": "2", "org": "NELC", "enrollment_end": "x",
        })

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"total": 3, "results": []})
        self.search.assert_called_once_with(
            search_term="data", size=10, from_=20, field_dictionary={"org": "NELC"},
        )
        self.track.emit.assert_has_calls([
            call("edx.course_discovery.search.initiated", {"search_term": "data", "page_size": 10, "page_number": 2}),
            call("edx.course_discovery.search.results_displayed",
                 {"search_term": "data", "page_size": 10, "page_number": 2, "results_count": 3}),
        ])

    def test_default_paging(self):
        """Without paging parameters the view asks for the first 20 results.

        Expected behavior:
            - size 20, from_ 0, no search term.
        """
        self.post({})

        self.search.assert_called_once_with(search_term=None, size=20, from_=0, field_dictionary={})

    @override_settings(SEARCH_MAX_PAGE_SIZE=50)
    def test_invalid_page_size_is_an_error(self):
        """A page size outside (0, SEARCH_MAX_PAGE_SIZE] answers 500 with the error, without searching.

        Expected behavior:
            - Status 500 and the invalid page size message, for 0 and for above the maximum.
        """
        for size in ("0", "51"):
            response = self.post({"page_size": size})

            self.assertEqual(response.status_code, 500)
            self.assertJSONEqual(response.content, {"error": f"Invalid page size of {size}"})
        self.search.assert_not_called()

    def test_search_failure_is_an_error(self):
        """Any search failure answers 500 with the upstream message and is logged.

        Expected behavior:
            - Status 500 and the generic error naming the search term.
        """
        self.search.side_effect = RuntimeError("invalid_search_filter")

        with self.assertLogs(VIEWS, level="ERROR"):
            response = self.post({"search_string": "data"})

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(response.content, {"error": 'An error occurred when searching for "data"'})

    def test_only_post_is_allowed(self):
        """Like upstream, the view only answers POST.

        Expected behavior:
            - GET answers 405.
        """
        request = self.factory.get(URL)
        request.user = AnonymousUser()

        self.assertEqual(course_discovery(request).status_code, 405)
