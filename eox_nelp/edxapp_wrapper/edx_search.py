"""Wrapper of edx-search.

Attributes:
    backend: Imported module by using the plugin settings.
    search_api: `search.api` (stock course_discovery_search, SearchFilterGenerator, SearchEngine, NoSearchEngineError).
    search_views: `search.views` (the stock `course_discovery` view).
    search_urls: `search.urls` (the URLPatterns mounted by the LMS under `search/`).
    search_meilisearch: `search.meilisearch` (`INDEX_FILTERABLES`, `MeilisearchEngine`, `get_search_params`,
        `process_results`).
    DateRange: `search.utils.DateRange`.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_EDX_SEARCH_BACKEND)

search_api = backend.get_search_api_module()
search_views = backend.get_search_views_module()
search_urls = backend.get_search_urls_module()
search_meilisearch = backend.get_search_meilisearch_module()
DateRange = backend.get_date_range_class()
