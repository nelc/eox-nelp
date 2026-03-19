"""
Test middlewares file.
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from django.test import override_settings

from eox_nelp.middleware import GCPCloudCDNSignedCookieMiddleware


class GCPCloudCDNSignedCookieMiddlewareTestCase(TestCase):
    """
    Unit tests for GCPCloudCDNSignedCookieMiddleware.
    """

    def setUp(self):
        """Setup common conditions for every test case."""
        self.middleware = GCPCloudCDNSignedCookieMiddleware(
            get_response=Mock()
        )

    @patch("eox_nelp.middleware.time.time", return_value=1700000000)
    def test_build_signed_cookie_value(self, _time_mock):
        """
        This method tests the desired behavior of _build_signed_cookie_value.
        Expected behavior:
            - Return a string value.
            - Return a value containing URLPrefix.
            - Return a value containing Expires with expected timestamp.
            - Return a value containing KeyName.
            - Return a value containing Signature.
        """
        result = self.middleware._build_signed_cookie_value()  # pylint: disable=protected-access

        self.assertIsInstance(result, str)
        self.assertIn("URLPrefix=", result)
        self.assertIn("Expires=1700003600", result)
        self.assertIn("KeyName=test-key", result)
        self.assertIn("Signature=", result)

    def test_sign_returns_valid_string(self):
        """
        This method tests the desired behavior of _sign.
        Expected behavior:
            - Return a string.
            - Return a non-empty value.
            - Return a value without '=' padding.
        """
        result = self.middleware._sign(b"test-data")  # pylint: disable=protected-access

        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertNotIn("=", result)

    @patch.object(
        GCPCloudCDNSignedCookieMiddleware,
        "_build_signed_cookie_value",
        return_value="signed-cookie-value",
    )
    def test_call_sets_cookie_for_authenticated_user(self, _mock_cookie):
        """
        This method tests the desired behavior of __call__ when the user
        is authenticated.
        Expected behavior:
            - get_response called once.
            - Response contains Set-Cookie header.
            - Set-Cookie contains cookie name.
        """
        request = Mock()
        request.user = Mock(is_authenticated=True)

        response = {}
        self.middleware.get_response = Mock(return_value=response)

        result = self.middleware(request)

        self.middleware.get_response.assert_called_once_with(request)
        self.assertIn("Set-Cookie", result)
        self.assertIn("Cloud-CDN-Cookie=", result["Set-Cookie"])

    def test_call_does_not_set_cookie_for_unauthenticated_user(self):
        """
        This method tests the desired behavior of __call__ when the user
        is not authenticated.
        Expected behavior:
            - get_response called once.
            - Response does not contain Set-Cookie header.
        """
        request = Mock()
        request.user = Mock(is_authenticated=False)

        response = {}
        self.middleware.get_response = Mock(return_value=response)

        result = self.middleware(request)

        self.middleware.get_response.assert_called_once_with(request)
        self.assertNotIn("Set-Cookie", result)

    @override_settings(GCP_CLOUD_CDN_COOKIE_DOMAIN="local.openedx.io")
    def test_call_sets_cookie_domain_when_cookie_domain_setting_exists(self):
        """
        This method tests the desired behavior of __call__ when the cookie
        domain setting exists.
        Expected behavior:
            - get_response called once.
            - Response contains Set-Cookie header.
            - Set-Cookie contains Domain with the configured value.
        """
        request = Mock()
        request.user = Mock(is_authenticated=True)

        response = {}
        self.middleware.get_response = Mock(return_value=response)

        result = self.middleware(request)

        self.middleware.get_response.assert_called_once_with(request)
        self.assertIn("Set-Cookie", result)
        self.assertIn("Domain=local.openedx.io", result["Set-Cookie"])
