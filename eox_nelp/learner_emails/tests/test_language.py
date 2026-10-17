"""Tests for the e-mail language chain: course -> learner -> English."""
from ddt import data, ddt, unpack
from django.test import TestCase

from eox_nelp.learner_emails.language import resolve_language


@ddt
class ResolveLanguageTestCase(TestCase):
    """The course language wins; unsupported or missing values fall to the next source."""

    @data(
        ("ar", "en", "ar"),
        ("en", "ar", "en"),
        ("fr", "ar", "fr"),
        ("fr_CA", None, "fr"),
        ("ar-SA", "fr", "ar"),
        (None, "ar", "ar"),
        ("", "fr", "fr"),
        ("ur", "ar", "ar"),
        ("ur", "xx", "en"),
        (None, None, "en"),
    )
    @unpack
    def test_resolve_language(self, course_language, user_language, expected):
        """Course language, then learner language, then English; unknown codes are skipped."""
        self.assertEqual(resolve_language(course_language, user_language), expected)
