"""Backend for edx-search.
This file contains all the necessary edx-search dependencies from
https://github.com/openedx/edx-search/tree/v4.1.3/search
"""
from search import api, meilisearch, urls, utils, views  # pylint: disable=import-error


def get_search_api_module():
    """Return the `search.api` module (course discovery search, filter generator, engine)."""
    return api


def get_search_views_module():
    """Return the `search.views` module (the stock `course_discovery` view)."""
    return views


def get_search_urls_module():
    """Return the `search.urls` module, whose URLPatterns the LMS mounts under `search/`."""
    return urls


def get_search_meilisearch_module():
    """Return `search.meilisearch` (INDEX_FILTERABLES, MeilisearchEngine, get_search_params, process_results)."""
    return meilisearch


def get_date_range_class():
    """Return `search.utils.DateRange`."""
    return utils.DateRange
