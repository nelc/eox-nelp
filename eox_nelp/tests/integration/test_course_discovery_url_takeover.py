"""Image-level check of the course discovery takeover. Run inside the BUILT image with the real LMS settings.

`EoxNelpConfig.ready()` swaps the callback of edx-search's own `course_discovery` route
(`init_pipeline.take_over_course_discovery_route`) and adds `end` to the course_info filterables.
"""
import pytest

pytest.importorskip("lms", reason="needs the edx-platform LMS (run in the built image)")


def test_course_discovery_url_resolves_to_the_eox_nelp_view():
    """/search/course_discovery/ must resolve to the eox-nelp view in the real URL conf."""
    # pylint: disable=import-outside-toplevel
    from django.urls import resolve

    from eox_nelp.course_discovery.views import course_discovery

    assert resolve("/search/course_discovery/").func is course_discovery


def test_course_end_is_a_course_info_filterable():
    """create_indexes() will make `end` filterable."""
    from search.meilisearch import INDEX_FILTERABLES  # pylint: disable=import-outside-toplevel,import-error

    assert "end" in INDEX_FILTERABLES["course_info"]
