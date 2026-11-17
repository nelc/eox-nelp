"""Tests for eox_nelp.course_discovery.api."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from eox_nelp.course_discovery.api import course_discovery_search, listing_filter, warn_stock_fallback
from eox_nelp.edxapp_wrapper.edx_search import search_api, search_meilisearch

NOW = datetime(2026, 11, 17, 8, 30)
API = "eox_nelp.course_discovery.api"
LISTING = listing_filter(NOW)


class ListingFilterTestCase(SimpleTestCase):
    """The rule sent to Meilisearch."""

    def test_open_enrollment_or_not_ended(self):
        """One OR group over both dates; a date missing from the document counts as open.

        Expected behavior:
            - The exact Meilisearch filter string.
        """
        timestamp = NOW.timestamp()

        self.assertEqual(
            listing_filter(NOW),
            f"(end >= {timestamp} OR end NOT EXISTS OR enrollment_end >= {timestamp} OR enrollment_end NOT EXISTS)",
        )


class CourseDiscoverySearchTestCase(SimpleTestCase):
    """With Meilisearch: the stock search plus the OR listing rule."""

    def setUp(self):
        self.searcher = search_meilisearch.MeilisearchEngine(index="course_info")
        self.searcher.meilisearch_index = MagicMock()
        self.searcher.meilisearch_index.search.return_value = {"hits": []}
        patchers = (
            patch(f"{API}.datetime", utcnow=MagicMock(return_value=NOW)),
            patch(f"{API}.search_api.SearchEngine.get_search_engine", return_value=self.searcher),
            patch(
                f"{API}.search_api.SearchFilterGenerator.generate_field_filters",
                return_value=({"org": "NELC", "course": "ignored"}, {"start_date": "ignored"}, {"org": ["Hidden"]}),
            ),
            patch(f"{API}.search_meilisearch.get_search_params", return_value={"filter": ['org = "NELC"']}),
            patch(f"{API}.search_meilisearch.process_results", return_value={"total": 0, "results": []}),
        )
        (_, self.get_search_engine, _, self.get_search_params, self.process_results) = (
            patcher.start() for patcher in patchers
        )
        for patcher in patchers:
            self.addCleanup(patcher.stop)

    def params_kwargs(self, **kwargs):
        """Run the search and return what it passed to get_search_params."""
        self.assertEqual(course_discovery_search(**kwargs), {"total": 0, "results": []})
        self.get_search_params.assert_called_once()
        return self.get_search_params.call_args.kwargs

    def test_sends_the_or_listing_rule(self):
        """The edx-search params plus one OR group, searched and converted as MeilisearchEngine.search does.

        Expected behavior:
            - The listing group is appended to the filters from get_search_params.
            - The index is searched with the term, and the results go through process_results.
        """
        course_discovery_search(search_term="data")

        self.searcher.meilisearch_index.search.assert_called_once_with(
            "data", {"filter": ['org = "NELC"', LISTING]},
        )
        self.process_results.assert_called_once_with({"hits": []}, "course_info")

    def test_no_enrollment_end_filter_outside_the_or_group(self):
        """The stock AND-ed enrollment_end filter is gone; only field and exclude rules reach get_search_params.

        Expected behavior:
            - No filter_dictionary, and no enrollment_end in the field or exclude dictionaries.
        """
        kwargs = self.params_kwargs()

        self.assertNotIn("filter_dictionary", kwargs)
        self.assertNotIn("enrollment_end", kwargs["field_dictionary"])
        self.assertNotIn("enrollment_end", kwargs["exclude_dictionary"])

    def test_listing_rule_without_other_filters(self):
        """get_search_params leaves out "filter" when there is no rule; the group is still sent.

        Expected behavior:
            - filter is exactly the listing group.
        """
        self.get_search_params.return_value = {"showRankingScore": True}

        course_discovery_search()

        self.searcher.meilisearch_index.search.assert_called_once_with(
            None, {"showRankingScore": True, "filter": [LISTING]},
        )

    def test_keeps_the_stock_arguments(self):
        """Org from the filter generator, request fields, exclusions, paging and aggregations as upstream.

        Expected behavior:
            - Only `org` is taken from the generator's field dictionary; its filter dictionary is ignored.
            - Request fields override it, and enrollment_start must be before now.
        """
        kwargs = self.params_kwargs(search_term="data", size=5, from_=10, field_dictionary={"language": "ar"})

        start = kwargs["field_dictionary"].pop("enrollment_start")
        self.assertEqual((start.lower, start.upper), (None, NOW))
        self.assertEqual(kwargs["field_dictionary"], {"org": "NELC", "language": "ar"})
        self.assertEqual(kwargs["exclude_dictionary"], {"org": ["Hidden"]})
        self.assertEqual((kwargs["size"], kwargs["from_"]), (5, 10))
        self.assertEqual(kwargs["aggregation_terms"], search_api.course_discovery_aggregations())
        self.get_search_engine.assert_called_once_with("course_info")

    @override_settings(SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING=True, COURSEWARE_INFO_INDEX_NAME="catalog")
    def test_honours_the_search_settings(self):
        """SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING drops the start filter; the index name is configurable.

        Expected behavior:
            - No enrollment_start in the field dictionary.
            - The engine is asked for the configured index.
        """
        kwargs = self.params_kwargs()

        self.assertEqual(kwargs["field_dictionary"], {"org": "NELC"})
        self.get_search_engine.assert_called_once_with("catalog")

    def test_no_search_engine_raises(self):
        """Without SEARCH_ENGINE the search raises the upstream error.

        Expected behavior:
            - NoSearchEngineError is raised.
        """
        self.get_search_engine.return_value = None

        with self.assertRaises(search_api.NoSearchEngineError):
            course_discovery_search()


class StockFallbackTestCase(SimpleTestCase):
    """Any other engine gets edx-search's stock search (stock rule), with one warning."""

    def setUp(self):
        warn_stock_fallback.cache_clear()
        self.addCleanup(warn_stock_fallback.cache_clear)

    def test_other_engine_uses_the_stock_search_and_warns_once(self):
        """Not a MeilisearchEngine: the stock search answers, the warning is logged once per engine class.

        Expected behavior:
            - The stock search gets the same arguments and its result is returned, twice.
            - One warning naming the engine class.
        """
        with patch(f"{API}.search_api.SearchEngine.get_search_engine", return_value=MagicMock()), \
                patch(f"{API}.search_api.course_discovery_search", return_value={"total": 1}) as stock, \
                self.assertLogs(API, level="WARNING") as logs:
            for _ in range(2):
                self.assertEqual(
                    course_discovery_search(search_term="data", size=5, from_=10, field_dictionary={"org": "X"}),
                    {"total": 1},
                )

        stock.assert_called_with(search_term="data", size=5, from_=10, field_dictionary={"org": "X"})
        self.assertEqual(stock.call_count, 2)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("MagicMock", logs.output[0])
