"""Image-level check of decision a2-url-takeover. Run inside the BUILT image with the real LMS settings.

    python manage.py lms test eox_nelp/tests/integration/test_enrollment_url_takeover.py   (or pytest in the image)

Plugin URL order is whatever stevedore yields, so nothing in this repo can guarantee that the
eox-nelp route is reached before eox-core's. If this fails, apply the decided fallback: replace
`eox_core.api.v1.views.EdxappEnrollment` from `EnrollmentApiConfig.ready()` with a startup
assertion, and pin tests that fail on any eox-core change.
"""
import pytest

pytest.importorskip("lms", reason="needs the edx-platform LMS (run in the built image)")


def test_enrollment_url_resolves_to_the_eox_nelp_view():
    """/eox-core/api/v1/enrollment/ must resolve to the eox-nelp view in the real URL conf."""
    from django.urls import resolve  # pylint: disable=import-outside-toplevel

    from eox_nelp.enrollment_api.views import NelpEdxappEnrollment  # pylint: disable=import-outside-toplevel

    assert resolve("/eox-core/api/v1/enrollment/").func.view_class is NelpEdxappEnrollment
