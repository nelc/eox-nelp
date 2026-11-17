"""Tests for eox_nelp.course_discovery.api."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from eox_nelp.course_discovery.api import course_discovery_search
from eox_nelp.edxapp_wrapper.edx_search import search_api

NOW = datetime(2026, 11, 17, 8, 30)
API = "eox_nelp.course_discovery.api"


class CourseDiscoverySearchTestCase(SimpleTestCase):
    """The eox-nelp search lists courses until they end; everything else is the stock search."""

    def setUp(self):
        self.searcher = MagicMock()
        self.searcher.search.return_value = {"total": 0, "results": []}
        patchers = (
            patch(f"{API}.datetime", utcnow=MagicMock(return_value=NOW)),
            patch(f"{API}.search_api.SearchEngine.get_search_engine", return_value=self.searcher),
            patch(
                f"{API}.search_api.SearchFilterGenerator.generate_field_filters",
                return_value=({"org": "NELC", "course": "ignored"}, {"start_date": "ignored"}, {"org": ["Hidden"]}),
            ),
        )
        _, self.get_search_engine, _ = (patcher.start() for patcher in patchers)
        for patcher in patchers:
            self.addCleanup(patcher.stop)

    def search_kwargs(self, **kwargs):
        """Run the search and return what it passed to the engine."""
        course_discovery_search(**kwargs)
        self.searcher.search.assert_called_once()
        return self.searcher.search.call_args.kwargs

    def test_filters_on_course_end_not_on_enrollment_end(self):
        """A course stays listed while its end is empty or in the future.

        Expected behavior:
            - The optional filter is `end` from now on, with no upper bound.
            - There is no `enrollment_end` filter anywhere.
        """
        kwargs = self.search_kwargs()

        self.assertEqual(list(kwargs["filter_dictionary"]), ["end"])
        end = kwargs["filter_dictionary"]["end"]
        self.assertEqual((end.lower, end.upper), (NOW, None))
        self.assertNotIn("enrollment_end", kwargs["field_dictionary"])
        self.assertNotIn("enrollment_end", kwargs["exclude_dictionary"])

    def test_keeps_the_stock_arguments(self):
        """Org from the filter generator, request fields, exclusions, paging and aggregations as upstream.

        Expected behavior:
            - Only `org` is taken from the generator's field dictionary; its filter dictionary is ignored.
            - Request fields override it, and enrollment_start must be before now.
        """
        kwargs = self.search_kwargs(search_term="data", size=5, from_=10, field_dictionary={"language": "ar"})

        start = kwargs["field_dictionary"].pop("enrollment_start")
        self.assertEqual((start.lower, start.upper), (None, NOW))
        self.assertEqual(kwargs["field_dictionary"], {"org": "NELC", "language": "ar"})
        self.assertEqual(kwargs["exclude_dictionary"], {"org": ["Hidden"]})
        self.assertEqual(
            (kwargs["query_string"], kwargs["size"], kwargs["from_"]), ("data", 5, 10),
        )
        self.assertEqual(kwargs["aggregation_terms"], search_api.course_discovery_aggregations())
        self.get_search_engine.assert_called_once_with("course_info")

    @override_settings(SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING=True, COURSEWARE_INFO_INDEX_NAME="catalog")
    def test_honours_the_search_settings(self):
        """SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING drops the start filter; the index name is configurable.

        Expected behavior:
            - No enrollment_start in the field dictionary, the end filter is still there.
            - The engine is asked for the configured index.
        """
        kwargs = self.search_kwargs()

        self.assertEqual(kwargs["field_dictionary"], {"org": "NELC"})
        self.assertIn("end", kwargs["filter_dictionary"])
        self.get_search_engine.assert_called_once_with("catalog")

    def test_no_search_engine_raises(self):
        """Without SEARCH_ENGINE the search raises the upstream error.

        Expected behavior:
            - NoSearchEngineError is raised.
        """
        self.get_search_engine.return_value = None

        with self.assertRaises(search_api.NoSearchEngineError):
            course_discovery_search()
