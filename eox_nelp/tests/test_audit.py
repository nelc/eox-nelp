"""
Test the caller audit helpers.
"""
import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from eox_nelp.audit import USER_AGENT_MAX_LENGTH, CallerAuditMixin, log_api_caller


def audit_records(logs):
    """Return the JSON payloads of the `api_caller_audit` lines captured by assertLogs."""
    return [json.loads(line.split("api_caller_audit ", 1)[1]) for line in logs.output]


class LogApiCallerTestCase(TestCase):
    """Test case for log_api_caller."""

    def setUp(self):
        """Setup common conditions for every test case."""
        self.factory = RequestFactory()

    def test_anonymous_request(self):
        """
        Test the record of an anonymous request.

        Expected behavior:
            - One line is logged.
            - The record names the surface, method, host, path and status.
            - The user fields are empty or false, and no authenticator is reported.
            - The client IP falls back to REMOTE_ADDR.
        """
        request = self.factory.get("/eox-nelp/stats/tenant/", HTTP_HOST="tenant.example.com")
        request.user = AnonymousUser()

        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            log_api_caller(request, "stats.tenant_page", status=200)

        self.assertEqual(
            audit_records(logs),
            [{
                "surface": "stats.tenant_page",
                "method": "GET",
                "host": "tenant.example.com",
                "route": None,
                "status": 200,
                "user_id": None,
                "is_staff": False,
                "is_superuser": False,
                "auth": None,
                "oauth_client_id": None,
                "client_ip": "127.0.0.1",
                "user_agent": "",
                "referer": None,
            }],
        )

    def test_authenticated_request_with_proxy_headers(self):
        """
        Test the record of an authenticated request that crossed Cloudflare and a proxy.

        Expected behavior:
            - The user id and flags are recorded, and the auth is reported as session.
            - The Cloudflare client IP wins over X-Forwarded-For.
            - The referer is reduced to scheme, host and path.
            - The user agent is truncated.
            - The extra fields are merged in.
        """
        request = self.factory.get(
            "/eox-nelp/api/users/v1/user/",
            HTTP_CF_CONNECTING_IP="203.0.113.7",
            HTTP_X_FORWARDED_FOR="198.51.100.1, 10.0.0.1",
            HTTP_REFERER="https://tenant.example.com/admin/page?email=someone@example.com",
            HTTP_USER_AGENT="a" * (USER_AGENT_MAX_LENGTH + 50),
        )
        request.user = Mock(id=7, is_authenticated=True, is_staff=True, is_superuser=False)

        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            log_api_caller(request, "users.v1.user", status=200, lookup_type="email")

        record = audit_records(logs)[0]
        self.assertEqual(record["user_id"], 7)
        self.assertTrue(record["is_staff"])
        self.assertFalse(record["is_superuser"])
        self.assertEqual(record["auth"], "session")
        self.assertEqual(record["client_ip"], "203.0.113.7")
        self.assertEqual(record["referer"], "https://tenant.example.com/admin/page")
        self.assertEqual(len(record["user_agent"]), USER_AGENT_MAX_LENGTH)
        self.assertEqual(record["lookup_type"], "email")
        self.assertNotIn("someone@example.com", logs.output[0])

    def test_forwarded_for_fallback_and_oauth_client(self):
        """
        Test the record of a request authenticated with an OAuth access token, without Cloudflare's header.

        Expected behavior:
            - The client IP is the first X-Forwarded-For hop.
            - The authenticator class name and the OAuth client id are recorded.
        """
        request = self.factory.get("/eox-nelp/api/stats/v1/tenant/", HTTP_X_FORWARDED_FOR="198.51.100.1, 10.0.0.1")
        request.user = Mock(id=3, is_authenticated=True, is_staff=False, is_superuser=False)
        request.auth = Mock(application=Mock(client_id="client-123"))
        request.successful_authenticator = type("BearerAuthentication", (), {})()

        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            log_api_caller(request, "stats.v1.tenant", status=200)

        record = audit_records(logs)[0]
        self.assertEqual(record["client_ip"], "198.51.100.1")
        self.assertEqual(record["auth"], "BearerAuthentication")
        self.assertEqual(record["oauth_client_id"], "client-123")


class AuditedView(CallerAuditMixin, APIView):
    """Minimal audited view."""

    authentication_classes = []
    permission_classes = []
    audit_surface = "test.surface"

    def get(self, _request):
        """Add an extra audit field and answer 200."""
        self.audit_extra["lookup_type"] = "username"

        return Response({"ok": True})


class CallerAuditMixinTestCase(TestCase):
    """Test case for CallerAuditMixin."""

    def setUp(self):
        """Setup common conditions for every test case."""
        self.request = APIRequestFactory().get("/test/")
        force_authenticate(self.request, user=Mock(id=5, is_authenticated=True, is_staff=False, is_superuser=False))

    def test_logs_surface_status_and_extra(self):
        """
        Test that the mixin logs once per request with the final status and the handler's extra fields.

        Expected behavior:
            - The response is unchanged.
            - One line carries the surface, the status and the extra field.
        """
        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            response = AuditedView.as_view()(self.request)

        self.assertEqual(response.status_code, 200)
        record = audit_records(logs)[0]
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(record["surface"], "test.surface")
        self.assertEqual(record["status"], 200)
        self.assertEqual(record["user_id"], 5)
        self.assertEqual(record["lookup_type"], "username")

    @patch("eox_nelp.audit.log_api_caller", side_effect=ValueError("boom"))
    def test_audit_failure_does_not_break_the_response(self, _log_mock):
        """
        Test that a failure while logging is swallowed.

        Expected behavior:
            - The view still answers 200.
            - The failure is logged as an exception.
        """
        with self.assertLogs("eox_nelp.audit", level="ERROR") as logs:
            response = AuditedView.as_view()(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("api_caller_audit failed for AuditedView", logs.output[0])
