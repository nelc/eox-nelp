"""Caller audit for sensitive API surfaces.

Records who calls an endpoint before its access rules are tightened, so the change can be sized from evidence
instead of guessed. One INFO line per request, prefixed `api_caller_audit` and followed by a JSON object, e.g.

    api_caller_audit {"surface": "users.v1.user", "status": 200, "user_id": 7, "lookup_type": "national_id", ...}

The record never carries lookup values (email, username, national ID); only the lookup type and numeric user ids.
For the same reason it logs the matched route pattern, not the request path, since some lookups sit in the path.

functions:
    log_api_caller: Emit the audit line for a request.

classes:
    CallerAuditMixin: DRF view mixin that emits the audit line once the response is final.
"""
import json
import logging
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

USER_AGENT_MAX_LENGTH = 200


def get_client_ip(request):
    """Return the client IP as seen by Cloudflare, falling back to the first proxy hop and then the socket peer."""
    meta = request.META
    forwarded_for = meta.get("HTTP_X_FORWARDED_FOR", "")

    return meta.get("HTTP_CF_CONNECTING_IP") or forwarded_for.split(",")[0].strip() or meta.get("REMOTE_ADDR")


def get_oauth_client_id(request):
    """Return the OAuth client id when the request was authenticated with a DOT access token, else None."""
    application = getattr(getattr(request, "auth", None), "application", None)

    return getattr(application, "client_id", None)


def log_api_caller(request, surface, status=None, **extra):
    """Emit one `api_caller_audit` line describing the caller of `surface`.

    Args:
        request: Django or DRF request.
        surface (str): Stable name of the audited endpoint.
        status (int): HTTP status code of the response.
        **extra: Endpoint-specific fields. They must not carry PII values.
    """
    user = getattr(request, "user", None)
    is_authenticated = bool(user and user.is_authenticated)
    authenticator = getattr(request, "successful_authenticator", None)
    referer = urlsplit(request.META.get("HTTP_REFERER", ""))
    resolver_match = getattr(request, "resolver_match", None)
    record = {
        "surface": surface,
        "method": request.method,
        "host": request.META.get("HTTP_HOST"),
        # The pattern, not request.path: a lookup value can sit in the path (certificates by national ID).
        "route": getattr(resolver_match, "route", None),
        "status": status,
        "user_id": user.id if is_authenticated else None,
        "is_staff": bool(is_authenticated and user.is_staff),
        "is_superuser": bool(is_authenticated and user.is_superuser),
        "auth": type(authenticator).__name__ if authenticator else ("session" if is_authenticated else None),
        "oauth_client_id": get_oauth_client_id(request),
        "client_ip": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:USER_AGENT_MAX_LENGTH],
        # Scheme, host and path only: a referer query string can carry PII.
        "referer": f"{referer.scheme}://{referer.netloc}{referer.path}" if referer.netloc else None,
        **extra,
    }
    logger.info(
        "api_caller_audit %s", json.dumps(record, sort_keys=True, default=str), extra={"event": "api_caller_audit"},
    )


class CallerAuditMixin:
    """DRF view mixin that logs the caller of every request once the response is final.

    Set `audit_surface` on the view. A handler can add endpoint-specific, non-PII fields to `self.audit_extra`.
    Logging never breaks the request: a failure is logged as an exception and the response is returned as is.
    """

    audit_surface = None

    def initial(self, request, *args, **kwargs):
        """Reset the per-request audit fields before the handler runs."""
        self.audit_extra = {}
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        """Emit the audit line with the final status code."""
        response = super().finalize_response(request, response, *args, **kwargs)

        try:
            log_api_caller(
                request,
                self.audit_surface or type(self).__name__,
                status=response.status_code,
                **getattr(self, "audit_extra", {}),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("api_caller_audit failed for %s", type(self).__name__)

        return response
