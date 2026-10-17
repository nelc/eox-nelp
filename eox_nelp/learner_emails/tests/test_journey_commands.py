# pylint: disable=too-many-instance-attributes,too-many-locals,missing-function-docstring
# pylint: disable=attribute-defined-outside-init,keyword-arg-before-vararg
"""Integration tests: the hourly command and the backfill, from selection to the (mocked) send."""
from datetime import datetime, timedelta
from datetime import timezone as tz
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase
from mock import MagicMock, patch

from eox_nelp.learner_emails import tasks
from eox_nelp.learner_emails.models import LEARNING_STARTS, REMINDER_END, REMINDER_PROGRESS, LearnerEmailLog

J = "eox_nelp.learner_emails.journey"
T = "eox_nelp.learner_emails.tasks"
CMD = "eox_nelp.management.commands.send_journey_emails"
BACKFILL = "eox_nelp.management.commands.backfill_learner_emails"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=tz.utc)
C1, C2 = "course-v1:KSU+A+1", "course-v1:SEU+B+1"


class FakePlatform:
    """A tiny in-memory platform: courses, enrolments, progress, and the tenant settings per org."""

    def __init__(self):
        self.courses = {C1: ("KSU", NOW - timedelta(minutes=30), NOW + timedelta(days=5)),
                        C2: ("SEU", NOW - timedelta(minutes=30), NOW + timedelta(days=5))}
        # (user_id, created, active)
        self.enrolments = {C1: [(1, NOW - timedelta(days=2), True), (2, NOW - timedelta(days=2), False),
                                (3, NOW + timedelta(minutes=-10), True), (4, NOW - timedelta(days=1), True)],
                           C2: [(1, NOW - timedelta(days=2), True)]}
        self.progress = {(1, C1): 0.5, (3, C1): 0.82, (4, C1): 1.0, (2, C1): 0.9, (1, C2): 0.75}
        self.certificates = set()
        self.settings = {}  # (org, key) -> value

    def rows(self, org):
        return [(cid, o, s, e) for cid, (o, s, e) in self.courses.items() if o == org]

    def start(self):
        """Patch every platform access of the journey code and return the stack of patchers."""
        fake = self

        def started(org, since, until):
            return [r for r in fake.rows(org) if since <= r[2] <= until]

        def running(org, now):
            return [r for r in fake.rows(org) if r[2] <= now and (r[3] is None or r[3] > now)]

        def ending(org, since, until):
            return [r for r in fake.rows(org) if r[3] and since <= r[3] <= until]

        def enrolled(course_id):
            return iter([(user, created) for user, created, active in fake.enrolments[course_id] if active])

        def progress(course_id, minimum):
            return iter([(u, p) for (u, c), p in fake.progress.items() if c == course_id and p >= minimum])

        patches = {
            f"{J}.list_orgs": lambda: sorted({o for o, _s, _e in fake.courses.values()}),
            f"{J}.find_started_courses": started,
            f"{J}.find_running_courses": running,
            f"{J}.find_courses_ending": ending,
            f"{J}.iter_enrollments": enrolled,
            f"{J}.iter_progress": progress,
            f"{T}.get_progress": lambda uid, cid: fake.progress.get((uid, str(cid)), 0.0),
            f"{T}.is_enrolled": lambda uid, cid: any(u == uid and a for u, _c, a in fake.enrolments[str(cid)]),
            f"{T}.has_certificate": lambda uid, cid: (uid, str(cid)) in fake.certificates,
        }
        self.patchers = [patch(name, side_effect=fn) for name, fn in patches.items()]
        for patcher in self.patchers:
            patcher.start()
        helpers = patch(f"{J}.configuration_helpers")
        mock = helpers.start()
        mock.get_value_for_org.side_effect = lambda org, key, default: fake.settings.get((org, key), default)
        self.patchers.append(helpers)
        self.sends = []
        user_model = patch(f"{T}.User")
        users = user_model.start()
        users.objects.select_related.return_value.get.side_effect = lambda id: SimpleNamespace(
            id=id, profile=SimpleNamespace(name=f"Learner {id}"))
        self.patchers.append(user_model)
        for name, value in {
            "bind_tenant_for_org": "ksu.example.com", "get_site_for_domain": MagicMock(),
            "get_course_overview": SimpleNamespace(display_name="Cyber", language="ar"),
            "get_user_language": None, "tenant_root_url": "https://ksu.example.com",
            "get_course_path": "/courses/x/course/", "get_base_context": {},
            "make_recipient": MagicMock(), "emulate_tenant_request": MagicMock(),
        }.items():
            p = patch(f"{T}.{name}", return_value=value)
            p.start()
            self.patchers.append(p)
        send = patch(f"{T}.send_and_confirm", side_effect=lambda message: self.sends.append(message) or True)
        send.start()
        self.patchers.append(send)
        # Celery is not configured in the unit tests: queueing a task = running its delivery right away.

        def run_now(kind, user_id, course_id):
            if kind == LEARNING_STARTS:
                tasks.deliver_learning_starts(user_id, course_id)
            else:
                tasks.deliver_completion_reminder(user_id, course_id, kind)

        queue = patch(f"{CMD}.queue_email", side_effect=run_now)
        queue.start()
        self.patchers.append(queue)
        domain = patch(f"{CMD}.tenant_domain_for_org", side_effect=lambda org: f"{org.lower()}.example.com")
        domain.start()
        self.patchers.append(domain)
        domain2 = patch(f"{BACKFILL}.tenant_domain_for_org", side_effect=lambda org: f"{org.lower()}.example.com")
        domain2.start()
        self.patchers.append(domain2)
        self.now = patch("django.utils.timezone.now", return_value=NOW)
        self.now.start()
        self.patchers.append(self.now)

    def stop(self):
        for patcher in self.patchers:
            patcher.stop()


class JourneyCommandsTestCase(TestCase):
    """One fake platform, real selectors, real log table, real delivery code (queueing runs it inline)."""

    def setUp(self):
        self.platform = FakePlatform()
        self.platform.start()
        self.addCleanup(self.platform.stop)

    def _run(self, command="send_journey_emails", *args):
        out = StringIO()
        call_command(command, *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def _rows(self, kind):
        rows = LearnerEmailLog.objects.filter(kind=kind)  # pylint: disable=no-member
        return set(rows.values_list("user_id", "course_id"))

    def _enable(self, org, *flags):
        for flag in flags:
            self.platform.settings[(org, flag)] = True

    def test_everything_is_off_by_default(self):
        """No tenant switch, nothing is queued or sent."""
        output = self._run()

        self.assertEqual(self.platform.sends, [])
        self.assertIn("0 e-mails queued", output)

    def test_learning_starts_goes_to_active_enrolments_created_before_the_start(self):
        """User 1 yes; 2 unenrolled before the start no; 3 enrolled after the start (got Message 4) no."""
        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED")

        self._run("send_journey_emails", "--kind", LEARNING_STARTS)

        self.assertEqual(self._rows(LEARNING_STARTS), {(1, C1), (4, C1)})
        self.assertEqual(len(self.platform.sends), 2)

    def test_second_run_sends_nothing_more(self):
        """The command run twice gives no duplicate."""
        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED", "COMPLETION_REMINDER_EMAIL_ENABLED")

        self._run()
        first = len(self.platform.sends)
        self._run()

        self.assertGreater(first, 0)
        self.assertEqual(len(self.platform.sends), first)

    def test_start_edited_later_does_not_send_again(self):
        """Message 3 is once per learner and course: a new start date inside the window changes nothing."""
        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED")
        self._run()
        sent = len(self.platform.sends)
        self.platform.courses[C1] = ("KSU", NOW - timedelta(minutes=20), NOW + timedelta(days=5))

        self._run()

        self.assertEqual(len(self.platform.sends), sent)

    def test_tenant_a_switch_never_enables_tenant_b(self):
        """Only KSU switched Message 3 on: SEU's learners get nothing."""
        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED")

        self._run()

        self.assertEqual({course for _user, course in self._rows(LEARNING_STARTS)}, {C1})

    def test_switch_must_be_exactly_true(self):
        """A string "true" or 1 does not switch anything on."""
        self.platform.settings[("KSU", "LEARNING_STARTS_EMAIL_ENABLED")] = "true"
        self.platform.settings[("SEU", "LEARNING_STARTS_EMAIL_ENABLED")] = 1

        self._run()

        self.assertEqual(self.platform.sends, [])

    def test_progress_reminder_selects_the_active_learners_at_or_over_the_threshold(self):
        """User 1 is at 50% (no); 3 jumped to 82% (yes); 4 is complete (no); 2 is unenrolled (no)."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")

        self._run("send_journey_emails", "--kind", REMINDER_PROGRESS)

        self.assertEqual(self._rows(REMINDER_PROGRESS), {(3, C1)})
        message = self.platform.sends[0]
        self.assertEqual((message.context["completed_percent"], message.context["remaining_percent"]), (82, 18))

    def test_tenant_threshold_override(self):
        """A tenant that sets 50% reaches user 1 (50%) as well."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self.platform.settings[("KSU", "COMPLETION_REMINDER_PROGRESS_PERCENT")] = 50

        self._run("send_journey_emails", "--kind", REMINDER_PROGRESS)

        self.assertEqual(self._rows(REMINDER_PROGRESS), {(1, C1), (3, C1)})

    def test_end_date_reminder_reports_the_actual_progress(self):
        """The course ends in 5 days: every active learner who is not done gets it, with their real percent."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")

        self._run("send_journey_emails", "--kind", REMINDER_END)

        sent = {m.context["full_name"]: m.context["completed_percent"] for m in self.platform.sends}
        self.assertEqual(sent, {"Learner 1": 50, "Learner 3": 82})  # 4 is complete; 2 is unenrolled

    def test_certificate_holders_get_no_reminder(self):
        """A learner who already holds the certificate is not nudged."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self.platform.certificates.add((3, C1))

        self._run("send_journey_emails", "--kind", REMINDER_PROGRESS)

        self.assertEqual(self._rows(REMINDER_PROGRESS), set())

    def test_end_window_edges(self):
        """The reminder fires at 7 and 3 days before the end and not at 7.1 or 2.9."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        for days, expected in ((7.1, 0), (7, 1), (3, 1), (2.9, 0)):
            self.platform.courses[C1] = ("KSU", NOW - timedelta(days=9), NOW + timedelta(days=days))
            self.platform.enrolments[C1] = [(1, NOW - timedelta(days=2), True)]
            LearnerEmailLog.objects.all().delete()  # pylint: disable=no-member
            self.platform.sends.clear()

            self._run("send_journey_emails", "--kind", REMINDER_END)

            self.assertEqual(len(self.platform.sends), expected, f"{days} days")

    def test_no_end_date_means_no_end_reminder(self):
        """An open-ended course has no deadline to remind about."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self.platform.courses[C1] = ("KSU", NOW - timedelta(days=9), None)

        self._run("send_journey_emails", "--kind", REMINDER_END)

        self.assertEqual(self.platform.sends, [])

    def test_dry_run_counts_per_tenant_and_kind_and_sends_nothing(self):
        """--dry-run reports the counts and queues nothing."""
        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED", "COMPLETION_REMINDER_EMAIL_ENABLED")

        output = self._run("send_journey_emails", "--dry-run")

        self.assertIn("ksu.example.com org=KSU kind=learning_starts: 2", output)
        self.assertIn("ksu.example.com org=KSU kind=reminder_progress: 1", output)
        self.assertIn("would be queued (dry run)", output)
        self.assertEqual(self.platform.sends, [])
        self.assertEqual(LearnerEmailLog.objects.count(), 0)  # pylint: disable=no-member

    def test_malformed_tenant_threshold_skips_that_tenant_only(self):
        """A bad value is logged and that org skipped; other tenants still run."""
        self._enable("KSU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self._enable("SEU", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self.platform.settings[("KSU", "COMPLETION_REMINDER_PROGRESS_PERCENT")] = "seventy"

        with self.assertLogs("eox_nelp.management.commands.send_journey_emails", level="ERROR"):
            self._run("send_journey_emails", "--kind", REMINDER_PROGRESS)

        self.assertEqual({course for _user, course in self._rows(REMINDER_PROGRESS)}, {C2})

    def test_backfill_dry_run_then_apply_then_the_command_sends_nothing(self):
        """The backfill ignores the switch, writes only with --apply, and afterwards enabling mails no one."""
        dry = self._run("backfill_learner_emails", "--org", "KSU")
        self.assertEqual(LearnerEmailLog.objects.count(), 0)  # pylint: disable=no-member
        self.assertIn("(dry run, use --apply)", dry)

        self._run("backfill_learner_emails", "--org", "KSU", "--apply")
        self.assertIn((1, C1), self._rows(LEARNING_STARTS))
        self.assertIn((3, C1), self._rows(REMINDER_PROGRESS))
        self.assertNotIn((1, C2), self._rows(LEARNING_STARTS))  # other tenant untouched

        self._enable("KSU", "LEARNING_STARTS_EMAIL_ENABLED", "COMPLETION_REMINDER_EMAIL_ENABLED")
        self._run()
        self.assertEqual(self.platform.sends, [])

    def test_backfill_requires_an_org(self):
        """Never "every tenant" by omission."""
        with self.assertRaises(Exception):
            self._run("backfill_learner_emails")
