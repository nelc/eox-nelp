"""Image-level check of decision a2-url-takeover. Run inside the BUILT image with the real LMS settings.

    python manage.py lms test eox_nelp/tests/integration/test_enrollment_url_takeover.py   (or pytest in the image)

`EoxNelpConfig.ready()` swaps the callback of eox-core's own `edxapp-enrollment` route
(`init_pipeline.take_over_core_enrollment_route`), so this must pass whatever the plugin order is.
"""
import pytest

pytest.importorskip("lms", reason="needs the edx-platform LMS (run in the built image)")


def test_enrollment_url_resolves_to_the_eox_nelp_view():
    """/eox-core/api/v1/enrollment/ must resolve to the eox-nelp view in the real URL conf."""
    from django.urls import resolve  # pylint: disable=import-outside-toplevel

    from eox_nelp.enrollment_api.views import NelpEdxappEnrollment  # pylint: disable=import-outside-toplevel

    assert resolve("/eox-core/api/v1/enrollment/").func.view_class is NelpEdxappEnrollment
