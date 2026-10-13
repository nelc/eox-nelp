"""Contract tests for the resolved view: HTTP shape, batch status, caps, request id."""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory, force_authenticate

from eox_nelp.enrollment_api.views import NelpEdxappEnrollment, caller_id

VIEWS = "eox_nelp.enrollment_api.views"
SERVICES = "eox_nelp.enrollment_api.services"
COURSE = "course-v1:Org+Course+Run"


def state(allowed=False, enrollment=False):
    """Stand-in for EmailEnrollmentState."""
    return Mock(allowed=allowed, enrollment=enrollment)


class EnrollmentViewTestCase(TestCase):
    """POST through the real view, eox-core serializer and batch loop; edx-platform pieces mocked."""

    def setUp(self):
        """Authenticated superuser, empty cache, mocked platform."""
        cache.clear()
        self.user = get_user_model().objects.create_superuser("caller", "caller@example.com", "pw")
        self.factory = APIRequestFactory()
        self.site = Site.objects.create(domain="tenant.example", name="tenant")
        started = [
            patch(f"{SERVICES}.enroll_email", return_value=(state(), state(allowed=True), None)),
            patch(f"{SERVICES}.get_course_overview", return_value=Mock(
                is_enrollment_open=Mock(return_value=True), has_ended=Mock(return_value=False))),
            patch(f"{SERVICES}.is_actively_enrolled", return_value=False),
            patch(f"{SERVICES}.user_on_site", return_value=True),
            patch(f"{SERVICES}.account_exists", return_value=False),
            patch(f"{SERVICES}.get_valid_course_key", side_effect=lambda course_id: course_id),
            patch(f"{SERVICES}.send_enrollment_mail"),
            patch("eox_core.api.v1.serializers.validate_org", return_value=True),
            patch(
                "eox_nelp.enrollment_api.serializers.check_edxapp_enrollment_is_valid", return_value=["User not found"],
            ),
            patch("eox_core.api.v1.serializers.get_valid_course_key", side_effect=lambda course_id: course_id),
            patch(f"{VIEWS}.get_edxapp_user", side_effect=NotFound("no user")),
        ]
        self.mocks = [patcher.start() for patcher in started]
        for patcher in started:
            self.addCleanup(patcher.stop)
        self.get_user = self.mocks[-1]
        self.validity = self.mocks[8]

    def post(self, body, **headers):
        """POST body to the view as the authenticated caller."""
        request = self.factory.post("/eox-core/api/v1/enrollment/", body, format="json", **headers)
        request.site = self.site  # set by the platform's site middleware in the LMS
        force_authenticate(request, user=self.user)
        return NelpEdxappEnrollment.as_view()(request)

    def item(self, email, **extra):
        """A request item."""
        return {"email": email, "course_id": COURSE, "mode": "honor", **extra}

    def test_single_reserve_is_200_with_result_and_request_id(self):
        """Unknown email: 200, result reserved, X-Request-ID generated."""
        response = self.post(self.item("new@example.com"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["result"], "reserved")
        self.assertNotIn("username", response.data)
        self.assertEqual(len(response["X-Request-ID"]), 32)

    def test_supplied_request_id_is_echoed_when_safe_and_replaced_when_not(self):
        """Safe ids pass; anything with spaces/newlines is replaced (log injection)."""
        self.assertEqual(self.post(self.item("a@example.com"), HTTP_X_REQUEST_ID="abc-123")["X-Request-ID"], "abc-123")
        self.assertNotEqual(self.post(self.item("a@example.com"), HTTP_X_REQUEST_ID="a b\nc")["X-Request-ID"], "a b\nc")

    def test_batch_is_200_when_all_ok_and_202_when_an_item_errors(self):
        """Mixed batch: the closed-course item errors, the status is 202, other items still done."""
        overview = self.mocks[1]

        ok_only = self.post([self.item("a@example.com"), self.item("b@example.com")])
        overview.side_effect = [overview.return_value, NotFound("Course not found")]
        mixed = self.post([self.item("a@example.com"), self.item("b@example.com")])

        self.assertEqual(ok_only.status_code, status.HTTP_200_OK)
        self.assertEqual([row["result"] for row in ok_only.data], ["reserved", "reserved"])
        self.assertEqual(mixed.status_code, status.HTTP_202_ACCEPTED)

    def test_closed_course_item_error_text(self):
        """Closed course: item carries error detail 'Enrollment closed', status 202."""
        self.mocks[1].return_value.is_enrollment_open.return_value = False

        response = self.post(self.item("a@example.com"))

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(str(response.data["error"]["detail"]), "Enrollment closed")

    def test_known_account_does_not_hide_other_validation_errors(self):
        """Only 'User not found' is lifted for an email-only item; a bad mode still fails the request."""
        self.validity.return_value = ["User not found", "Mode not found"]

        response = self.post(self.item("a@example.com"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Mode not found", str(response.data))
        self.assertNotIn("User not found", str(response.data))

    def test_unknown_username_still_fails_the_request(self):
        """A username that does not exist keeps eox-core's 400."""
        response = self.post({"username": "ghost", "course_id": COURSE, "mode": "honor"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_body_is_400(self):
        """eox-core's serializer still rejects a bad body."""
        response = self.post({"email": "a@example.com"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_more_than_100_items_rejected_with_400(self):
        """The whole request is rejected before any item runs."""
        response = self.post([self.item(f"u{i}@example.com") for i in range(101)])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("100", str(response.data))
        self.mocks[0].assert_not_called()

    def test_hourly_cap_rejects_with_429(self):
        """1,000 items pass for a caller; the next request is refused."""
        for _ in range(10):
            self.assertEqual(self.post([self.item(f"u{i}@example.com") for i in range(100)]).status_code, 200)

        response = self.post(self.item("late@example.com"))

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_existing_account_uses_the_eox_core_create_path(self):
        """Account found: eox-core's create_enrollment runs (mode honoured) and the item says enrolled."""
        account = Mock(email="known@example.com")
        self.get_user.side_effect = None
        self.get_user.return_value = account
        enrollment = {"user": "known", "mode": "honor", "is_active": True, "course_id": COURSE}
        with patch("eox_core.api.v1.views.create_enrollment", return_value=(enrollment, [])) as create:
            response = self.post(self.item("known@example.com"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["result"], "enrolled")
        self.assertEqual(create.call_args.kwargs["mode"], "honor")

    def test_caller_id_prefers_the_oauth_application(self):
        """OAuth callers are keyed by application, others by user."""
        request = Mock(auth=Mock(application=Mock(client_id="cid")), user=Mock(pk=5))
        self.assertEqual(caller_id(request), "app-cid")
        request = Mock(auth=None, user=Mock(pk=5))
        self.assertEqual(caller_id(request), "user-5")
