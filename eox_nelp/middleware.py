"""Middleware file.

Required NELP middlewares that allow customizing edx-platform.
"""

import base64
import hashlib
import hmac
import time

from django.conf import settings


class GCPCloudCDNSignedCookieMiddleware:
    """
    Middleware that generates and attaches a Google Cloud CDN signed cookie.

    The cookie is only generated for authenticated users and is signed using
    the key configured for the Cloud CDN backend bucket.
    """

    COOKIE_NAME = "Cloud-CDN-Cookie"

    def __init__(self, get_response):
        """
        Initialize middleware with Django's response handler.
        """
        self.get_response = get_response

    def _sign(self, data: bytes) -> str:
        """
        Generate the HMAC-SHA1 signature required by Google Cloud CDN.

        - Decodes the base64url key from settings.
        - Signs the payload using HMAC-SHA1.
        - Returns a base64url-encoded signature without padding.

        Args:
            data (bytes): The payload to sign.

        Returns:
            str: Base64url-encoded signature.
        """
        key = base64.urlsafe_b64decode(
            settings.GCP_CLOUD_CDN_SIGNING_KEY + "===="
        )
        signature = hmac.new(key, data, hashlib.sha1).digest()

        return base64.urlsafe_b64encode(signature).decode().rstrip("=")

    def _build_signed_cookie_value(self) -> str:
        """
        Build the full Google Cloud CDN signed cookie value.

        Includes:
        - URLPrefix (base64url)
        - Expires (UNIX timestamp)
        - KeyName
        - Signature

        Required format:
        URLPrefix=...:Expires=...:KeyName=...:Signature=...

        Returns:
            str: Final cookie value.
        """
        expires = int(time.time()) + settings.GCP_CLOUD_CDN_COOKIE_MAX_AGE

        encoded_prefix = base64.urlsafe_b64encode(
            settings.GCP_CLOUD_CDN_URL_PREFIX.encode()
        ).decode().rstrip("=")

        policy = (
            f"URLPrefix={encoded_prefix}:"
            f"Expires={expires}:"
            f"KeyName={settings.GCP_CLOUD_CDN_SIGNING_KEY_NAME}"
        )

        signature = self._sign(policy.encode())

        return f"{policy}:Signature={signature}"

    def __call__(self, request):
        """
        Process each request and attach the signed cookie to the response
        if the user is authenticated.

        The cookie is manually constructed to avoid Django adding quotes,
        which would break Cloud CDN validation.
        """
        response = self.get_response(request)

        if (user := getattr(request, "user", None)) and user.is_authenticated:
            cookie_value = self._build_signed_cookie_value()

            parts = [
                f"{self.COOKIE_NAME}={cookie_value}",
                f"Max-Age={settings.GCP_CLOUD_CDN_COOKIE_MAX_AGE}",
                "Path=/",
            ]

            if cookie_domain := getattr(
                settings, "GCP_CLOUD_CDN_COOKIE_DOMAIN", None
            ):
                parts.append(f"Domain={cookie_domain}")

            response["Set-Cookie"] = "; ".join(parts)

        return response
