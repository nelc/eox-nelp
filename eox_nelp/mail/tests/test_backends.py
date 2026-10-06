"""Tests for the pooled SMTP email backend. ``smtplib.SMTP`` is mocked: nothing here touches a network."""
import smtplib
import threading
from unittest.mock import MagicMock, call, patch

from django.core import mail
from django.test import TestCase, override_settings

from eox_nelp.mail import backends

BACKEND = "eox_nelp.mail.backends.PooledSMTPEmailBackend"
SECRET_PASSWORD = "s3cret-smtp-password"  # nosec - fake credential used to prove it is never logged
SECRET_BODY = "secret-body-text"


def new_message():
    """Return a throwaway message to hand to ``send_messages``."""
    return mail.EmailMessage("Subject", "Body", "from@example.test", ["to@example.test"])


@override_settings(
    EMAIL_BACKEND=BACKEND,
    EMAIL_HOST="smtp.example.test",
    EMAIL_PORT=587,
    EMAIL_USE_TLS=True,
    EMAIL_HOST_USER="smtp-user",
    EMAIL_HOST_PASSWORD=SECRET_PASSWORD,
)
class PooledSMTPEmailBackendBase(TestCase):
    """A fake ``smtplib.SMTP``, a controllable clock and a ``send`` helper shared by the test cases below."""

    def setUp(self):
        """Start with an empty pool, a fake SMTP class and a controllable clock."""
        backends._sessions().clear()  # pylint: disable=protected-access
        self.connections = []
        smtp_patcher = patch("smtplib.SMTP", side_effect=self.new_connection)
        self.smtp = smtp_patcher.start()
        self.addCleanup(smtp_patcher.stop)

        clock_patcher = patch("eox_nelp.mail.backends.time")
        self.clock = clock_patcher.start()
        self.addCleanup(clock_patcher.stop)
        self.now = 1000.0
        self.clock.monotonic.side_effect = lambda: self.now

    def new_connection(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Build the fake connection ``smtplib.SMTP(...)`` returns and remember it."""
        connection = MagicMock(name=f"connection-{len(self.connections)}")
        self.connections.append(connection)
        return connection

    def new_connection_that_drops(self, *args, **kwargs):
        """Like ``new_connection`` but the connection's ``sendmail`` always reports a disconnect."""
        connection = self.new_connection(*args, **kwargs)
        connection.sendmail.side_effect = smtplib.SMTPServerDisconnected()
        return connection

    @staticmethod
    def send(count=1, **kwargs):
        """Send ``count`` messages through Django's normal ``mail.send_mail`` path, like edx-ace does."""
        return [
            mail.send_mail("Subject", SECRET_BODY, "from@example.test", ["to@example.test"], **kwargs)
            for _ in range(count)
        ]


class SessionLifecycleTestCase(PooledSMTPEmailBackendBase):
    """When sessions are opened, reused, recycled and kept apart."""

    def test_session_is_reused_across_sends(self):
        """Three separate sends share one connect + STARTTLS + AUTH and never QUIT."""
        self.assertEqual(self.send(3), [1, 1, 1])

        self.assertEqual(len(self.connections), 1)
        connection = self.connections[0]
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with("smtp-user", SECRET_PASSWORD)
        self.assertEqual(connection.sendmail.call_count, 3)
        connection.quit.assert_not_called()

    def test_close_keeps_the_session_for_the_next_backend(self):
        """Leaving a ``with get_connection()`` block hands the session back instead of QUITting."""
        for _ in range(2):
            with mail.get_connection() as connection:
                connection.send_messages([new_message()])

        self.assertEqual(len(self.connections), 1)
        self.connections[0].quit.assert_not_called()

    def test_idle_session_is_recycled(self):
        """A session unused for longer than the idle limit is closed and replaced."""
        self.send()
        self.now += 4
        self.send()
        self.assertEqual(len(self.connections), 1)

        self.now += 6  # over the 5 s default, under SES's ~10 s server-side idle close
        self.send()

        self.assertEqual(len(self.connections), 2)
        self.connections[0].quit.assert_called_once()
        self.connections[1].sendmail.assert_called_once()

    @override_settings(EOX_NELP_SMTP_POOL_MAX_IDLE_SECONDS=60)
    def test_idle_limit_is_a_setting(self):
        """The idle limit comes from settings."""
        self.send()
        self.now += 30
        self.send()

        self.assertEqual(len(self.connections), 1)

    @override_settings(EOX_NELP_SMTP_POOL_MAX_MESSAGES=2)
    def test_session_is_recycled_after_max_messages(self):
        """The third message goes out on a new session once two were sent on the first."""
        self.send(3)

        self.assertEqual(len(self.connections), 2)
        self.assertEqual(self.connections[0].sendmail.call_count, 2)
        self.connections[0].quit.assert_called_once()
        self.assertEqual(self.connections[1].sendmail.call_count, 1)

    @override_settings(EOX_NELP_SMTP_POOL_MAX_MESSAGES=2)
    def test_one_long_batch_respects_max_messages(self):
        """The limit applies inside a single ``send_messages`` call too, not only between calls."""
        messages = [new_message() for _ in range(5)]

        self.assertEqual(mail.get_connection().send_messages(messages), 5)

        self.assertEqual([c.sendmail.call_count for c in self.connections], [2, 2, 1])

    @override_settings(EOX_NELP_SMTP_POOL_MAX_AGE_SECONDS=10)
    def test_session_is_recycled_after_max_age(self):
        """A busy session still gets replaced once it is older than the age limit."""
        for _ in range(3):  # t = 0, 4, 8: never idle, still young
            self.send()
            self.now += 4
        self.assertEqual(len(self.connections), 1)

        self.send()  # t = 12: older than 10 s

        self.assertEqual(len(self.connections), 2)
        self.connections[0].quit.assert_called_once()

    def test_sessions_are_not_shared_between_threads(self):
        """Another thread opens its own session and does not disturb this thread's."""
        self.send()
        worker = threading.Thread(target=self.send, args=(2,))
        worker.start()
        worker.join()

        self.assertEqual(len(self.connections), 2)
        self.assertEqual(self.connections[0].sendmail.call_count, 1)
        self.assertEqual(self.connections[1].sendmail.call_count, 2)

        self.send()  # this thread keeps reusing its own session

        self.assertEqual(len(self.connections), 2)
        self.assertEqual(self.connections[0].sendmail.call_count, 2)

    def test_session_inherited_through_fork_is_dropped_not_reused_or_quit(self):
        """In a forked child the parent's session is abandoned: no reuse, and no QUIT that would end the parent's."""
        self.send()
        with patch("eox_nelp.mail.backends.os.getpid", return_value=424242):
            self.send()

        self.assertEqual(len(self.connections), 2)
        self.connections[0].quit.assert_not_called()
        self.connections[0].close.assert_not_called()

    def test_different_logins_do_not_share_a_session(self):
        """Backends configured with different credentials never borrow each other's authenticated session."""
        for username in ("user-a", "user-b", "user-a"):
            mail.get_connection(username=username, password="x").send_messages([new_message()])

        self.assertEqual(len(self.connections), 2)
        self.assertEqual([c.login.call_args for c in self.connections], [call("user-a", "x"), call("user-b", "x")])

    def test_nothing_sensitive_is_logged(self):
        """Recycling logs the relay and the reason, never credentials or message content."""
        self.send()
        self.now += 10
        with self.assertLogs("eox_nelp.mail.backends", level="DEBUG") as logs:
            self.send()

        output = "\n".join(logs.output)
        self.assertIn("idle too long", output)
        self.assertIn("smtp.example.test:587", output)
        for secret in (SECRET_PASSWORD, SECRET_BODY, "smtp-user", "to@example.test"):
            self.assertNotIn(secret, output)


class FailureHandlingTestCase(PooledSMTPEmailBackendBase):
    """What happens when the server drops a session or a send fails."""

    def test_dropped_session_is_replaced_and_message_resent_once(self):
        """If the server dropped the reused session, the message goes out on a fresh one."""
        self.send()
        self.connections[0].sendmail.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        self.connections[0].quit.side_effect = smtplib.SMTPServerDisconnected()  # a dead session cannot QUIT politely

        self.assertEqual(self.send(), [1])

        self.assertEqual(len(self.connections), 2)
        self.assertEqual(self.connections[0].sendmail.call_count, 2)  # the first send and the failed one
        self.connections[1].sendmail.assert_called_once()
        failed_attempt, resend = self.connections[0].sendmail.call_args_list[1], self.connections[1].sendmail.call_args
        self.assertEqual(failed_attempt.args[:2], resend.args[:2])  # same sender and recipients: the same message
        self.connections[0].close.assert_called()  # force-closed because QUIT could not be sent

    def test_broken_socket_is_treated_as_dropped_session(self):
        """A reset or broken pipe on a reused session gets the same single reconnect."""
        self.send()
        self.connections[0].sendmail.side_effect = BrokenPipeError()

        self.assertEqual(self.send(), [1])

        self.assertEqual(len(self.connections), 2)

    def test_reconnect_is_attempted_only_once(self):
        """If the fresh session is dropped as well the error surfaces: no retry loop."""
        self.send()
        self.connections[0].sendmail.side_effect = smtplib.SMTPServerDisconnected()
        self.smtp.side_effect = self.new_connection_that_drops

        with self.assertRaises(smtplib.SMTPServerDisconnected):
            self.send()

        self.assertEqual(len(self.connections), 2)

    def test_disconnect_on_a_fresh_session_is_not_retried(self):
        """A brand-new session that is dropped immediately behaves like the stock backend: it raises."""
        self.smtp.side_effect = self.new_connection_that_drops

        with self.assertRaises(smtplib.SMTPServerDisconnected):
            self.send()

        self.assertEqual(len(self.connections), 1)

    def test_other_smtp_errors_propagate_and_close_the_session(self):
        """A refusal is not retried, reaches the caller, and the next send starts clean."""
        self.send()
        self.connections[0].sendmail.side_effect = smtplib.SMTPDataError(554, b"Message rejected")

        with self.assertRaises(smtplib.SMTPDataError):
            self.send()

        self.assertEqual(len(self.connections), 1)
        self.connections[0].quit.assert_called_once()  # closed on error
        self.assertEqual(self.send(), [1])
        self.assertEqual(len(self.connections), 2)

    def test_fail_silently_swallows_smtp_errors_like_stock(self):
        """With ``fail_silently=True`` an SMTP error returns 0, as in Django's own backend."""
        self.send()
        self.connections[0].sendmail.side_effect = smtplib.SMTPDataError(554, b"Message rejected")

        self.assertEqual(self.send(fail_silently=True), [0])

        self.connections[0].quit.assert_called_once()

    def test_fail_silently_does_not_swallow_non_smtp_errors(self):
        """Like the stock backend, only SMTP errors are silenced; the session is still closed."""
        self.send()
        self.connections[0].sendmail.side_effect = ValueError("boom")

        with self.assertRaises(ValueError):
            self.send(fail_silently=True)

        self.connections[0].quit.assert_called_once()

    def test_connect_failure_follows_fail_silently(self):
        """Failing to connect raises, or returns 0 under ``fail_silently``, exactly like the stock backend."""
        self.smtp.side_effect = OSError("network unreachable")

        with self.assertRaises(OSError):
            self.send()
        self.assertEqual(self.send(fail_silently=True), [0])

    def test_failure_to_reconnect_follows_fail_silently(self):
        """When the replacement session cannot be opened, ``fail_silently`` decides, as for any first connect."""
        self.send()
        self.connections[0].sendmail.side_effect = smtplib.SMTPServerDisconnected()
        self.smtp.side_effect = OSError("network unreachable")

        self.assertEqual(self.send(fail_silently=True), [0])

        self.smtp.side_effect = self.new_connection  # network is back; then the server drops it again
        self.send()
        self.connections[-1].sendmail.side_effect = smtplib.SMTPServerDisconnected()
        self.smtp.side_effect = OSError("network unreachable")
        with self.assertRaises(OSError):
            self.send()

    @override_settings(EOX_NELP_SMTP_POOL_MAX_MESSAGES=1)
    def test_failure_to_recycle_follows_fail_silently(self):
        """When a session due for recycling cannot be replaced inside a batch, ``fail_silently`` decides."""
        connection = mail.get_connection(fail_silently=True)
        self.smtp.side_effect = [self.new_connection(), OSError("network unreachable")]

        self.assertEqual(connection.send_messages([new_message(), new_message()]), 1)
