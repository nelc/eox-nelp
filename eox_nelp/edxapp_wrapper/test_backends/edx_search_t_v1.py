"""Backend test abstraction of edx-search: small stand-ins with the shape of the real modules."""
from types import SimpleNamespace

from django.http import HttpResponse
from django.urls import path


class DateRange:
    """Stand-in of search.utils.DateRange."""

    def __init__(self, lower=None, upper=None):
        self.lower = lower
        self.upper = upper


class NoSearchEngineError(Exception):
    """Stand-in of search.api.NoSearchEngineError."""


class SearchFilterGenerator:
    """Stand-in of search.filter_generator.SearchFilterGenerator."""

    @classmethod
    def generate_field_filters(cls, **kwargs):  # pylint: disable=unused-argument
        """Field, filter and exclude dictionaries."""
        return {}, {}, {}


class SearchEngine:
    """Stand-in of search.search_engine_base.SearchEngine."""

    @staticmethod
    def get_search_engine(index=None):  # pylint: disable=unused-argument
        """No engine configured."""
        return None


def stock_view(request, **kwargs):  # pylint: disable=unused-argument
    """Stands in for every stock edx-search view."""
    return HttpResponse("stock")


class MeilisearchEngine:
    """Stand-in of search.meilisearch.MeilisearchEngine."""

    def __init__(self, index=None):
        self.index_name = index
        self.meilisearch_index = None


def get_search_params(**kwargs):  # pylint: disable=unused-argument
    """Stand-in of search.meilisearch.get_search_params."""
    return {"showRankingScore": True}


def process_results(results, index_name):  # pylint: disable=unused-argument
    """Stand-in of search.meilisearch.process_results."""
    return results


search_api = SimpleNamespace(
    SearchFilterGenerator=SearchFilterGenerator,
    SearchEngine=SearchEngine,
    NoSearchEngineError=NoSearchEngineError,
    course_discovery_filter_fields=lambda: ["org", "modes", "language"],
    course_discovery_aggregations=lambda: {"org": {}, "modes": {}, "language": {}},
    course_discovery_search=lambda **kwargs: {"total": 0, "results": []},
)
search_views = SimpleNamespace(course_discovery=stock_view, do_search=stock_view)
search_urls = SimpleNamespace(urlpatterns=[
    path("", stock_view, name="do_search"),
    path("course_discovery/", stock_view, name="course_discovery"),
])
search_meilisearch = SimpleNamespace(
    INDEX_FILTERABLES={
        "course_info": ["language", "modes", "org", "catalog_visibility", "enrollment_end"],
        "courseware_content": ["_pk", "course", "org", "catalog_visibility", "start_date"],
    },
    MeilisearchEngine=MeilisearchEngine,
    get_search_params=get_search_params,
    process_results=process_results,
)


def get_search_api_module():
    """Test search.api."""
    return search_api


def get_search_views_module():
    """Test search.views."""
    return search_views


def get_search_urls_module():
    """Test search.urls."""
    return search_urls


def get_search_meilisearch_module():
    """Test search.meilisearch."""
    return search_meilisearch


def get_date_range_class():
    """Test search.utils.DateRange."""
    return DateRange
