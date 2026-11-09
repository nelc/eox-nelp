"""Tests for the backfill_lti_activity_completions command."""
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase
from mock import Mock, patch

MODULE = "eox_nelp.management.commands.backfill_lti_activity_completions"


@patch(f"{MODULE}.complete_lti_block_from_ags_score")
@patch(f"{MODULE}.LtiAgsScore")
class BackfillLtiActivityCompletionsTestCase(SimpleTestCase):
    """Dry run by default; filters per course; --apply, --user-id and --limit are passed through."""

    def _run(self, score_mock, *args):
        out = StringIO()
        queryset = score_mock.objects.filter.return_value.select_related.return_value.order_by.return_value
        queryset.iterator.side_effect = lambda: iter([Mock(), Mock(), Mock()])
        call_command("backfill_lti_activity_completions", *args, stdout=out)

        return out.getvalue()

    def test_dry_run(self, score_mock, complete_mock):
        """Default mode passes apply=False and filters on the course's blocks."""
        complete_mock.return_value = "completed"

        output = self._run(score_mock, "--course-key", "course-v1:mcit+aws+T1")

        score_mock.objects.filter.assert_called_once_with(
            activity_progress="Completed",
            score_given__isnull=True,
            line_item__resource_link_id__startswith="block-v1:mcit+aws+T1+",
        )
        self.assertEqual(complete_mock.call_args.kwargs, {"apply": False, "only_user_id": None})
        self.assertIn("3 LTI blocks would be completed", output)

    def test_apply_with_user_and_limit(self, score_mock, complete_mock):
        """--apply and --user-id reach the function; --limit stops after that many completions across courses."""
        complete_mock.return_value = "completed"

        output = self._run(
            score_mock, "--course-key", "course-v1:mcit+aws+T1", "--course-key", "course-v1:mcit+ai+T1",
            "--user-id", "7", "--limit", "2", "--apply",
        )

        self.assertEqual(complete_mock.call_count, 2)
        self.assertEqual(complete_mock.call_args.kwargs, {"apply": True, "only_user_id": 7})
        self.assertIn("2 LTI blocks completed.", output)
        self.assertIn("course-v1:mcit+ai+T1: {}", output)
