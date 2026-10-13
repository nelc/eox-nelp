"""Tests for the caps (Django cache counter) and the audit helpers."""
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from eox_nelp.enrollment_api import audit
from eox_nelp.enrollment_api.caps import HourlyCapExceeded, OverCap, check_caps, quota_key


class CapsTestCase(SimpleTestCase):
    """100 items per request, 1000 per caller per hour."""

    def setUp(self):
        """Start from an empty counter."""
        cache.clear()

    def test_exactly_the_request_cap_is_allowed(self):
        """100 items pass."""
        check_caps("app-a", 100)

    def test_over_the_request_cap_is_rejected_and_not_counted(self):
        """101 items: 400-style rejection that spends no quota."""
        with self.assertRaises(OverCap):
            check_caps("app-a", 101)

        self.assertIsNone(cache.get(quota_key("app-a")))

    def test_hourly_cap_rejects_and_hands_the_count_back(self):
        """1000 pass, the next item is rejected and does not consume quota."""
        for _ in range(10):
            check_caps("app-a", 100)

        with self.assertRaises(HourlyCapExceeded) as raised:
            check_caps("app-a", 1)

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(cache.get(quota_key("app-a")), 1000)

    def test_callers_are_counted_separately(self):
        """One caller's usage never blocks another."""
        for _ in range(10):
            check_caps("app-a", 100)

        check_caps("app-b", 100)

    @override_settings(EOX_NELP_ENROLLMENT_MAX_ITEMS=2, EOX_NELP_ENROLLMENT_HOURLY_LIMIT=3)
    def test_limits_come_from_settings(self):
        """The numbers are settings (defaults are the decided 100/1000)."""
        check_caps("app-a", 2)
        with self.assertRaises(HourlyCapExceeded):
            check_caps("app-a", 2)
        with self.assertRaises(OverCap):
            check_caps("app-a", 3)


class AuditTestCase(SimpleTestCase):
    """user_ref and the log line."""

    def test_user_ref_is_stable_case_insensitive_and_not_the_email(self):
        """Same person -> same ref; different salt -> different ref."""
        ref = audit.user_ref("Person@Example.com ")

        self.assertEqual(ref, audit.user_ref("person@example.com"))
        self.assertNotIn("person", ref)
        with override_settings(EOX_NELP_ENROLLMENT_LOG_SALT="other"):
            self.assertNotEqual(ref, audit.user_ref("person@example.com"))

    @override_settings(EOX_NELP_ENROLLMENT_LOG_SALT="")
    def test_missing_salt_fails_loudly(self):
        """No default salt exists: an unset salt is a configuration error, not a silent weak hash."""
        with self.assertRaises(ImproperlyConfigured):
            audit.user_ref("a@b.c")

    def test_log_event_renders_absent_fields_and_spaces(self):
        """`-` for absent values; spaces replaced so the line stays key=value parseable."""
        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            audit.log_event(request_id="r 1", outcome="reserved")

        self.assertIn("request_id=r_1", logs.output[0])
        self.assertIn("email_result=-", logs.output[0])
