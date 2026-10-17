"""Boundary tests for the timed learner e-mail rules (Message 3 and Message 5)."""
from datetime import datetime, timedelta
from datetime import timezone as tz

from ddt import data, ddt, unpack
from django.test import TestCase
from mock import patch

from eox_nelp.learner_emails.journey import (
    JourneyConfigError,
    end_window_due,
    enrolled_before_start,
    learning_starts_due,
    progress_due,
    reminder_thresholds,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=tz.utc)
HELPERS = "eox_nelp.learner_emails.journey.configuration_helpers"


@ddt
class LearningStartsRulesTestCase(TestCase):
    """Message 3: due right after the start, only for enrolments created before it."""

    @data(
        (timedelta(0), True),  # start == now
        (-timedelta(minutes=59), True),
        (-timedelta(hours=3), True),  # edge of the catch-up window
        (-timedelta(hours=3, seconds=1), False),
        (timedelta(seconds=1), False),  # not started yet
    )
    @unpack
    def test_learning_starts_due(self, offset, expected):
        """Start == now counts; the future and the long past do not."""
        self.assertEqual(learning_starts_due(NOW + offset, NOW), expected)

    def test_no_start_date_is_never_due(self):
        """A course without a start date has no start moment to announce (it counts as open for Message 4)."""
        self.assertFalse(learning_starts_due(None, NOW))

    @data((-timedelta(days=1), True), (-timedelta(seconds=1), True), (timedelta(0), False), (timedelta(hours=1), False))
    @unpack
    def test_enrolled_before_start(self, offset, expected):
        """Created before the start gets Message 3; at or after the start got Message 4 instead."""
        self.assertEqual(enrolled_before_start(NOW + offset, NOW), expected)

    def test_enrolment_without_a_date_is_not_before_start(self):
        """An unknown creation date never qualifies."""
        self.assertFalse(enrolled_before_start(None, NOW))


@ddt
class CompletionReminderRulesTestCase(TestCase):
    """Message 5: progress at/over the threshold and not complete; end date inside the window."""

    @data((0.699, False), (0.7, True), (0.82, True), (0.29, False), (0.9999, True), (1.0, False), (0, False))
    @unpack
    def test_progress_due_at_70(self, percent, expected):
        """69.9 no, 70 yes, a jump to 82 yes (one-sided rule), 100 no (complete)."""
        self.assertEqual(progress_due(percent, 70), expected)

    def test_progress_threshold_float_noise(self):
        """0.29 * 100 is 28.999999999999996 in floating point: the comparison must not lose the learner."""
        self.assertTrue(progress_due(0.29, 29))

    @data(
        (2.9, False), (3, True), (5, True), (7, True), (7.1, False), (0, False),
    )
    @unpack
    def test_end_window_due(self, days, expected):
        """3 to 7 days before the end, both ends included."""
        self.assertEqual(end_window_due(NOW + timedelta(days=days), NOW, 3, 7), expected)

    def test_no_end_date_is_never_in_the_window(self):
        """Open-ended courses have no deadline to remind about."""
        self.assertFalse(end_window_due(None, NOW, 3, 7))


@ddt
class ReminderThresholdsTestCase(TestCase):
    """Tenant overrides of the business values."""

    @patch(HELPERS)
    def test_business_values_when_the_tenant_sets_nothing(self, helpers):
        """Unset keys give the business values, 70% and 3 to 7 days."""
        helpers.get_value_for_org.side_effect = lambda org, key, default: default

        self.assertEqual(reminder_thresholds("KSU"), (70, (3, 7)))

    @patch(HELPERS)
    def test_tenant_overrides(self, helpers):
        """A tenant can set its own threshold and window."""
        values = {"COMPLETION_REMINDER_PROGRESS_PERCENT": 50, "COMPLETION_REMINDER_END_WINDOW_DAYS": [1, 2.5]}
        helpers.get_value_for_org.side_effect = lambda org, key, default: values.get(key, default)

        self.assertEqual(reminder_thresholds("KSU"), (50, (1, 2.5)))

    @data(
        ("COMPLETION_REMINDER_PROGRESS_PERCENT", "70"),
        ("COMPLETION_REMINDER_PROGRESS_PERCENT", 0),
        ("COMPLETION_REMINDER_PROGRESS_PERCENT", 100),
        ("COMPLETION_REMINDER_PROGRESS_PERCENT", True),
        ("COMPLETION_REMINDER_END_WINDOW_DAYS", [7, 3]),
        ("COMPLETION_REMINDER_END_WINDOW_DAYS", [3]),
        ("COMPLETION_REMINDER_END_WINDOW_DAYS", "3-7"),
        ("COMPLETION_REMINDER_END_WINDOW_DAYS", [-1, 7]),
    )
    @unpack
    @patch(HELPERS)
    def test_malformed_value_is_an_error_not_the_default(self, key, value, helpers):
        """A bad tenant value is reported, never silently replaced by the business value."""
        helpers.get_value_for_org.side_effect = lambda org, name, default: value if name == key else default

        with self.assertRaises(JourneyConfigError):
            reminder_thresholds("KSU")
