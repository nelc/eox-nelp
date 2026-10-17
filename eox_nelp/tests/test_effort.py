"""Tests for the Effort -> localized hours formatter and its template filter."""
from ddt import data, ddt, unpack
from django.template import Context, Template
from django.test import TestCase
from django.utils import translation

from eox_nelp.effort import format_effort_hours


@ddt
class FormatEffortHoursTestCase(TestCase):
    """Parsing and pluralisation, in each shipped language."""

    @data(
        ("en", "40:00", "40 hours"),
        ("en", "40:30", "40 hours and 30 minutes"),
        ("en", "0:30", "30 minutes"),
        ("en", "1:01", "1 hour and 1 minute"),
        ("en", "4", "4 hours"),
        ("en", "1", "1 hour"),
        ("en", "1.5", "1.5 hours"),
        ("en", "2.50", "2.5 hours"),
        ("en", " 40 ", "40 hours"),
        ("en", "٤", "4 hours"),  # Arabic-Indic digits typed by an author are numbers too
        ("fr", "1", "1 heure"),
        ("fr", "2", "2 heures"),
        ("fr", "40:30", "40 heures et 30 minutes"),
        ("ar", "1", "ساعة واحدة"),
        ("ar", "2", "ساعتان"),
        ("ar", "4", "4 ساعات"),
        ("ar", "11", "11 ساعة"),
        ("ar", "40", "40 ساعة"),
        ("ar", "100", "100 ساعة"),
        ("ar", "40:30", "40 ساعة و30 دقيقة"),
        ("ar", "1.5", "1.5 ساعة"),
    )
    @unpack
    def test_formats(self, language, effort, expected):
        """Hours (plus non-zero minutes) with the language's plural form."""
        with translation.override(language):
            self.assertEqual(format_effort_hours(effort), expected)

    @data("", "   ", None)
    def test_blank_gives_empty(self, effort):
        """A blank value is empty so templates can hide the line."""
        self.assertEqual(format_effort_hours(effort), "")

    @data("about a week", "40 hours", "1:75", "1,5", "-4")
    def test_unparsable_is_returned_exactly_as_typed(self, effort):
        """Text that is not one of the three forms is never guessed at."""
        self.assertEqual(format_effort_hours(effort), effort)

    def test_unparsable_keeps_its_spaces(self):
        """As typed means as typed, spaces included."""
        self.assertEqual(format_effort_hours(" about a week "), " about a week ")

    def test_template_filter(self):
        """The filter is the same function, usable from a Django template."""
        template = Template("{% load eox_nelp_tags %}{{ effort|effort_hours }}")

        with translation.override("en"):
            self.assertEqual(template.render(Context({"effort": "40:30"})), "40 hours and 30 minutes")
