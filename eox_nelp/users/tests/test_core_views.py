"""Tests for the create-user takeover: rejected fields answer 400, and the route runs our view."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from eox_core.api.v1 import urls as core_urls
from eox_core.api.v1.views import EdxappUser as CoreEdxappUser
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from eox_nelp.init_pipeline import CORE_USER_ROUTE, take_over_core_user_route
from eox_nelp.users.core_views import NelpEdxappUser

CREATE = "eox_core.api.v1.views.create_edxapp_user"
BODY = {"username": "learner_1", "email": "learner@example.com", "password": "pw-12345", "fullname": "A Learner"}


class NelpEdxappUserTestCase(TestCase):
    """POST through the real eox-core view and serializer; account creation mocked."""

    def setUp(self):
        """Authenticated superuser on a tenant site."""
        self.caller = get_user_model().objects.create_superuser("caller", "caller@example.com", "pw")
        self.site = Site.objects.create(domain="tenant.example", name="tenant")
        self.factory = APIRequestFactory()
        for patcher in (
            patch("eox_core.api.v1.serializers.check_edxapp_account_conflicts", return_value=[]),
            patch("eox_core.api.v1.views.get_current_site", return_value=self.site),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, body):
        """POST body to the view as the authenticated caller."""
        request = self.factory.post("/eox-core/api/v1/user/", body, format="json")
        force_authenticate(request, user=self.caller)
        return NelpEdxappUser.as_view()(request)

    @patch(CREATE, side_effect=DjangoValidationError({"username": ["invalid characters"]}))
    def test_field_error_is_400_with_the_field(self, _create):
        """The case seen in prod: do_create_account rejects one field."""
        response = self.post(BODY)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"username": ["invalid characters"]})

    @patch(CREATE, side_effect=DjangoValidationError({"username": ["invalid characters"]}))
    def test_without_override_eox_core_lets_the_error_escape(self, _create):
        """Why the override exists: eox-core's own view raises it uncaught, which the LMS serves as a 500."""
        request = self.factory.post("/eox-core/api/v1/user/", BODY, format="json")
        force_authenticate(request, user=self.caller)

        with self.assertRaises(DjangoValidationError):
            CoreEdxappUser.as_view()(request)

    @patch(CREATE, side_effect=DjangoValidationError({
        "national_id": ["already exists"], "username": ["invalid characters"],
    }))
    def test_every_rejected_field_is_returned(self, _create):
        """Several rejected fields all reach the caller."""
        response = self.post(BODY)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {"national_id", "username"})

    @patch(CREATE, side_effect=DjangoValidationError("no field attached"))
    def test_error_without_fields_is_a_400_list(self, _create):
        """A plain ValidationError (no field dict) still answers 400."""
        response = self.post(BODY)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, ["no field attached"])

    @patch(CREATE)
    def test_success_is_unchanged(self, create):
        """A created user still answers 200 through eox-core's own serializer."""
        create.return_value = (get_user_model().objects.create_user("learner_1", "learner@example.com"), [])

        response = self.post(BODY)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "learner_1")

    @patch(CREATE, side_effect=RuntimeError("database down"))
    def test_other_errors_are_not_masked(self, _create):
        """Only validation errors become 400; a real fault still raises (500)."""
        with self.assertRaises(RuntimeError):
            self.post(BODY)

    def test_missing_required_field_is_still_eox_core_400(self):
        """eox-core's serializer check runs first, as before."""
        response = self.post({"email": "learner@example.com"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserRouteTakeoverTestCase(TestCase):
    """The eox-core create-user route runs the eox-nelp view, and drift is loud."""

    def setUp(self):
        """Restore eox-core's route after each test."""
        self.route = next(route for route in core_urls.urlpatterns if route.name == CORE_USER_ROUTE)
        self.addCleanup(setattr, self.route, "callback", self.route.callback)

    def test_takeover_points_the_route_at_our_view(self):
        """After the takeover the route's view class is NelpEdxappUser (idempotent)."""
        take_over_core_user_route()
        take_over_core_user_route()

        self.assertIs(self.route.callback.view_class, NelpEdxappUser)

    def test_missing_route_fails_loudly(self):
        """eox-core renaming the route must stop startup, never silently keep its view."""
        self.route.name = "renamed-upstream"
        self.addCleanup(setattr, self.route, "name", CORE_USER_ROUTE)

        with self.assertRaises(ImproperlyConfigured):
            take_over_core_user_route()

    def test_view_keeps_eox_core_docs(self):
        """The API docs schema eox-core attaches to post survives the override."""
        self.assertEqual(NelpEdxappUser.post.__doc__, CoreEdxappUser.post.__doc__)
