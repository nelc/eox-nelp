"""Course discovery search with the eox-nelp listing rule.

Same as `search.api.course_discovery_search` in edx-search 4.1.3 except for the optional filter: the stock
search keeps a course while its `enrollment_end` is empty or in the future, this one while its `end` is.
"""
from datetime import datetime

from django.conf import settings

from eox_nelp.edxapp_wrapper.edx_search import DateRange, search_api

COURSE_INFO_INDEX = "course_info"  # edx-search default of COURSEWARE_INFO_INDEX_NAME


def course_info_index_name():
    """Name of the course discovery index."""
    return getattr(settings, "COURSEWARE_INFO_INDEX_NAME", COURSE_INFO_INDEX)


def course_discovery_search(search_term=None, size=20, from_=0, field_dictionary=None):
    """
    Course Discovery activities against the search engine index of course details.

    Lists the courses that have not ended: no end date, or an end date in the future.
    """
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

    searcher = search_api.SearchEngine.get_search_engine(course_info_index_name())
    if not searcher:
        raise search_api.NoSearchEngineError("No search engine specified in settings.SEARCH_ENGINE")

    return searcher.search(
        query_string=search_term,
        size=size,
        from_=from_,
        # only show when enrollment start IS provided and is before now
        field_dictionary=use_field_dictionary,
        # show if no course end is provided or it has not yet been reached
        filter_dictionary={"end": DateRange(datetime.utcnow(), None)},
        exclude_dictionary=exclude_dictionary,
        aggregation_terms=search_api.course_discovery_aggregations(),
    )
