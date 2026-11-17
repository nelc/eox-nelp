"""Course discovery search with the eox-nelp listing rule.

Same as `search.api.course_discovery_search` in edx-search 4.1.3 except for the listing rule. The stock search
keeps a course while enrollment is open (`enrollment_end` empty or in the future). This one keeps it while
enrollment is open OR the course has not ended (`end` empty or in the future), so nothing the stock rule lists
disappears.

edx-search's engines AND every rule, so the OR cannot go through `SearchEngine.search()`. With Meilisearch this
module does what `MeilisearchEngine.search` does (`get_search_params`, `meilisearch_index.search`,
`process_results`) and adds the OR group to the filter. Any other engine falls back to the stock search.
"""
import logging
from datetime import datetime
from functools import lru_cache

from django.conf import settings

from eox_nelp.edxapp_wrapper.edx_search import DateRange, search_api, search_meilisearch

log = logging.getLogger(__name__)

COURSE_INFO_INDEX = "course_info"  # edx-search default of COURSEWARE_INFO_INDEX_NAME
LISTING_DATE_FIELDS = ("end", "enrollment_end")  # a course is listed while either is empty or in the future


def course_info_index_name():
    """Name of the course discovery index."""
    return getattr(settings, "COURSEWARE_INFO_INDEX_NAME", COURSE_INFO_INDEX)


def listing_filter(now):
    """
    Meilisearch filter: the course has not ended OR its enrollment is open.

    Each half is what edx-search's `get_filter_rule(field, DateRange(now, None), optional=True)` writes, so a
    field missing from the document (no date set) counts as open.
    """
    timestamp = now.timestamp()
    rules = [f"{field} >= {timestamp} OR {field} NOT EXISTS" for field in LISTING_DATE_FIELDS]
    return f"({' OR '.join(rules)})"


@lru_cache(maxsize=None)
def warn_stock_fallback(engine_class_name):
    """Log once per engine class that the stock listing rule is used."""
    log.warning(
        "Course discovery: %s is not a MeilisearchEngine; using edx-search's stock listing rule "
        "(courses are listed only while enrollment is open).",
        engine_class_name,
    )


def course_discovery_search(search_term=None, size=20, from_=0, field_dictionary=None):
    """
    Course Discovery activities against the search engine index of course details.

    Lists the courses whose enrollment is open or that have not ended.
    """
    searcher = search_api.SearchEngine.get_search_engine(course_info_index_name())
    if not searcher:
        raise search_api.NoSearchEngineError("No search engine specified in settings.SEARCH_ENGINE")
    if not isinstance(searcher, search_meilisearch.MeilisearchEngine):
        warn_stock_fallback(type(searcher).__name__)
        return search_api.course_discovery_search(
            search_term=search_term, size=size, from_=from_, field_dictionary=field_dictionary,
        )

    # Only the org of the filter generator is used; the enrollment dates are handled here, as upstream does.
    use_search_fields = ["org"]
    (search_fields, _, exclude_dictionary) = search_api.SearchFilterGenerator.generate_field_filters()
    use_field_dictionary = {
        field: search_fields[field]
        for field in search_fields if field in use_search_fields
    }
    if field_dictionary:
        use_field_dictionary.update(field_dictionary)
    if not getattr(settings, "SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING", False):
        use_field_dictionary["enrollment_start"] = DateRange(None, datetime.utcnow())

    params = search_meilisearch.get_search_params(
        field_dictionary=use_field_dictionary,
        exclude_dictionary=exclude_dictionary,
        aggregation_terms=search_api.course_discovery_aggregations(),
        size=size,
        from_=from_,
    )
    params.setdefault("filter", []).append(listing_filter(datetime.utcnow()))
    results = searcher.meilisearch_index.search(search_term, params)
    return search_meilisearch.process_results(results, searcher.index_name)
