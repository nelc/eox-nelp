"""Pin tests: fail when an edx-search update changes what eox_nelp.course_discovery copies or relies on.

They need edx-search itself, so they run only where it is installed (the LMS image, or a test environment
with `edx-search==4.1.3`), and are skipped elsewhere.
"""
import hashlib
import importlib.util
import inspect
from unittest import skipUnless

from django.test import SimpleTestCase

HAS_EDX_SEARCH = importlib.util.find_spec("search") is not None and \
    importlib.util.find_spec("search.meilisearch") is not None

# sha256 of inspect.getsource(...) in edx-search 4.1.3.
UPSTREAM_SOURCES_SHA256 = {
    "search.api.course_discovery_search": "448287f43961d4771fa0f998cec2c92b29f1c57495e3dcd8a9b8f013ed81d90c",
    "search.views.course_discovery": "1a0bfa46b6199e6a03be2e1ad733bd28e9a3ebcf694edf292383fb482a90ce0b",
    "search.views._process_pagination_values": "72f56bc3b174e89617fb9c6a169474e1e11eed21419c3eca262d9108ef4e5343",
    "search.views._process_field_values": "ed5220aefd90de92329d7a4b597a027cf5d5d9e44c9f5a2493eca8f37cb9507b",
}


@skipUnless(HAS_EDX_SEARCH, "needs edx-search")
class EdxSearchContractTestCase(SimpleTestCase):
    """What the override assumes about edx-search still holds."""

    def test_copied_sources_are_unchanged(self):
        """The search, view and helpers we copied are still the 4.1.3 ones (review the copy if not)."""
        # pylint: disable=import-outside-toplevel,import-error
        from search import api, views

        for name, expected in UPSTREAM_SOURCES_SHA256.items():
            module = {"search.api": api, "search.views": views}[name.rsplit(".", 1)[0]]
            source = inspect.getsource(getattr(module, name.rsplit(".", 1)[1]))
            with self.subTest(name):
                self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), expected)

    def test_discovery_route_is_unique_and_named(self):
        """`take_over_course_discovery_route` finds this route by name and swaps its callback."""
        from search import urls, views  # pylint: disable=import-outside-toplevel,import-error

        named = [entry for entry in urls.urlpatterns if entry.name == "course_discovery"]
        self.assertEqual(len(named), 1)
        self.assertEqual(str(named[0].pattern), "course_discovery/")
        self.assertIn(named[0].callback, (views.course_discovery, self.ours()))

    def test_course_info_filterables_are_a_list_keyed_by_index_name(self):
        """`make_course_end_filterable` appends to this list before `create_indexes()` reads it."""
        from search import meilisearch  # pylint: disable=import-outside-toplevel,import-error

        self.assertIsInstance(meilisearch.INDEX_FILTERABLES["course_info"], list)
        self.assertIn("enrollment_end", meilisearch.INDEX_FILTERABLES["course_info"])

    def test_optional_range_filter_keeps_courses_without_end(self):
        """The Meilisearch filter for our `end` range also matches documents with no `end`."""
        # pylint: disable=import-outside-toplevel,import-error
        from search.meilisearch import get_filter_rule
        from search.utils import DateRange

        rule = get_filter_rule("end", DateRange(1, None), optional=True)
        self.assertEqual(rule, "end >= 1 OR end NOT EXISTS")

    @staticmethod
    def ours():
        """The eox-nelp view (the route holds it once the takeover ran)."""
        from eox_nelp.course_discovery.views import course_discovery  # pylint: disable=import-outside-toplevel
        return course_discovery
