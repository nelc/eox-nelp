"""Pin tests: fail loudly when an eox-core update changes what the override copies or relies on.

Run on every eox-core bump (decision a2-url-takeover).
"""
import importlib.util
import re
from unittest.mock import patch

from django.test import SimpleTestCase
from eox_core.api.v1 import views as core_views

from eox_nelp.enrollment_api.serializers import USER_NOT_FOUND
from eox_nelp.enrollment_api.views import NelpEdxappEnrollment

COURSE = "course-v1:Org+Course+Run"
QUERY = {"email": "a@example.com", "course_id": COURSE, "mode": "honor"}


class CoreContractTestCase(SimpleTestCase):
    """What the override assumes about eox-core exists and still behaves the same."""

    def test_core_attributes_the_override_relies_on_exist(self):
        """Class, hook methods and the decorator we re-apply."""
        core = core_views.EdxappEnrollment
        for name in ("post", "put", "delete", "single_enrollment_create", "single_enrollment_update",
                     "prepare_multiresponse", "get_user_query"):
            self.assertTrue(callable(getattr(core, name)), name)
        self.assertTrue(callable(core_views.audit_drf_api))
        self.assertTrue(issubclass(NelpEdxappEnrollment, core))

    def test_user_not_found_wording_is_still_what_eox_core_returns(self):
        """Our serializer filters this exact string out of eox-core's validation errors."""
        spec = importlib.util.find_spec("eox_core.edxapp_wrapper.backends.enrollment_o_v1")
        with open(spec.origin, encoding="utf-8") as source:
            self.assertIn(f"return ['{USER_NOT_FOUND}']", source.read())

    def test_enrollment_url_is_still_a_single_route_in_core(self):
        """Our regex takes `enrollment/` exactly; core must not grow sub-routes beneath it."""
        from eox_core.api.v1 import urls  # pylint: disable=import-outside-toplevel

        patterns = [str(entry.pattern) for entry in urls.urlpatterns]
        self.assertEqual([p for p in patterns if re.match(r"\^enrollment", p)], ["^enrollment/$"])

    def test_batch_loop_matches_eox_cores_for_ok_and_failing_items(self):
        """Same status and body as core's loop (non-reserve input), item errors included."""
        def action(**query):
            if query["email"] == "bad@example.com":
                raise core_views.ValidationError("boom")
            return [{"email": query["email"], "ok": True}]

        for body in (dict(QUERY), [dict(QUERY), {**QUERY, "email": "bad@example.com"}]):
            with patch("eox_core.api.v1.serializers.check_edxapp_enrollment_is_valid", return_value=[]), \
                    patch("eox_nelp.enrollment_api.serializers.check_edxapp_enrollment_is_valid", return_value=[]), \
                    patch("eox_core.api.v1.serializers.validate_org", return_value=True), \
                    patch("eox_core.api.v1.serializers.get_valid_course_key", side_effect=str):
                core = core_views.EdxappEnrollment.prepare_multiresponse(body, action)
                ours = NelpEdxappEnrollment.prepare_multiresponse(body, action)

            self.assertEqual(ours.status_code, core.status_code)
            self.assertEqual(ours.data, core.data)
