"""Pin tests: fail when an edx-search update changes what eox_nelp.course_discovery copies or relies on.

They need edx-search itself, so they run only where it is installed (the LMS image, or a test environment
with `edx-search==4.1.3`), and are skipped elsewhere.
"""
import hashlib
import importlib.util
import inspect
from datetime import datetime
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
    # Reproduced by eox_nelp.course_discovery.api to add the OR listing group.
    "search.meilisearch.MeilisearchEngine.search": "267b232f13ab71056b460fbaee77b4bf8d4539092e969985645c7df9121cff80",
    "search.meilisearch.get_search_params": "b4576e12473e268419a8df97fbf758ab2a185147c3081a25a3ebf9e0a2624f76",
    "search.meilisearch.process_results": "4aea661b68a7653e5e356467a514f46cff766aed94367de4b93fb8b86e98de3d",
}


@skipUnless(HAS_EDX_SEARCH, "needs edx-search")
class EdxSearchContractTestCase(SimpleTestCase):
    """What the override assumes about edx-search still holds."""

    def test_copied_sources_are_unchanged(self):
        """The search, view, helpers and Meilisearch steps we copy or call are the 4.1.3 ones (review if not)."""
        # pylint: disable=import-outside-toplevel,import-error
        from search import api, meilisearch, views

        modules = {"search.api": api, "search.views": views, "search.meilisearch": meilisearch}
        for name, expected in UPSTREAM_SOURCES_SHA256.items():
            module_name, _, attribute_path = name.partition(".")[2].partition(".")
            target = modules[f"search.{module_name}"]
            for attribute in attribute_path.split("."):
                target = getattr(target, attribute)
            source = inspect.getsource(target)
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

    def test_listing_filter_is_edx_search_rules_joined_by_or(self):
        """Each half of our OR group is what edx-search writes for an optional open-ended date range."""
        # pylint: disable=import-outside-toplevel,import-error
        from search.meilisearch import get_filter_rule
        from search.utils import DateRange

        from eox_nelp.course_discovery.api import LISTING_DATE_FIELDS, listing_filter

        now = datetime(2026, 11, 17, 8, 30)
        rules = [get_filter_rule(field, DateRange(now, None), optional=True) for field in LISTING_DATE_FIELDS]
        self.assertEqual(listing_filter(now), f"({' OR '.join(rules)})")

    def test_meilisearch_engine_exposes_what_the_search_uses(self):
        """`meilisearch_index` and `index_name` are what MeilisearchEngine.search itself uses."""
        from search.meilisearch import MeilisearchEngine  # pylint: disable=import-outside-toplevel,import-error

        engine = MeilisearchEngine(index="course_info")
        self.assertEqual(engine.index_name, "course_info")
        self.assertIsInstance(MeilisearchEngine.__dict__["meilisearch_index"], property)

    @staticmethod
    def ours():
        """The eox-nelp view (the route holds it once the takeover ran)."""
        from eox_nelp.course_discovery.views import course_discovery  # pylint: disable=import-outside-toplevel
        return course_discovery
