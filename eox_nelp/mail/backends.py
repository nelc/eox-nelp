"""Email backend that keeps one authenticated SMTP session open per process and thread.

Django's stock SMTP backend opens a connection (TCP connect + STARTTLS + AUTH) for every
message sent through ``mail.send()``, because ``get_connection()`` builds a fresh backend each
time. With a remote relay (e.g. Amazon SES from another region) that handshake costs about two
seconds per message. This backend amortises it: the first message opens a session, later
messages on the same thread reuse it.

Enable it with ``EMAIL_BACKEND = "eox_nelp.mail.backends.PooledSMTPEmailBackend"``. It takes the
same ``EMAIL_HOST``/``EMAIL_PORT``/``EMAIL_HOST_USER``/... settings as the stock backend, plus
these optional ones (read on every send, so they can be changed without a restart):

``EOX_NELP_SMTP_POOL_MAX_IDLE_SECONDS`` (default 5)
    Reconnect if the session sat unused longer than this. Amazon SES closes an idle SMTP
    connection after about 10 seconds, so the default stays well under that.
``EOX_NELP_SMTP_POOL_MAX_MESSAGES`` (default 100)
    Reconnect after this many messages on one session.
``EOX_NELP_SMTP_POOL_MAX_AGE_SECONDS`` (default 300)
    Reconnect once the session is this old, however busy it was.

Amazon SES documents no fixed message-count or age limit. Its "Amazon SES SMTP issues" page says the
SMTP endpoint runs behind a load balancer whose instances are periodically replaced, so a client
should open a new connection after a fixed number of messages or some active time, and find the
thresholds by experiment. Its SMTP command-line page says the connection closes after about 10
seconds of inactivity (error ``451 Timeout waiting for data from client``). The count and age
defaults are therefore starting points, not documented limits; the idle default is derived from the
documented 10 seconds. Sources, fetched 2026-10-06:
https://docs.aws.amazon.com/ses/latest/dg/troubleshoot-smtp.html and
https://docs.aws.amazon.com/ses/latest/dg/send-email-smtp-client-command-line.html

Safety properties:

* One session per (process, thread, relay settings). A session is never shared between threads,
  and a session inherited through ``fork()`` (uWSGI, Celery prefork) is dropped, never reused.
* If the server dropped a reused session, the message is sent again once on a fresh session. The
  server may have accepted the message before dropping, so that one message can in rare cases
  be delivered twice (at-least-once). Every other failure behaves like the stock backend.
* Nothing is logged except the reason a session was recycled and the relay host and port.
"""
import logging
import os
import smtplib
import ssl
import threading
import time

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)

# Failures that mean "the server (or the network) dropped our session", as opposed to a refusal
# of this particular message. Only these are retried.
SESSION_DROPPED = (smtplib.SMTPServerDisconnected, ConnectionError, ssl.SSLEOFError)

# Per-thread {relay key: _Session}. Threads never see each other's sessions.
_local = threading.local()


class _Session:
    """An open SMTP connection plus the facts needed to decide when to recycle it."""

    def __init__(self, connection):
        self.connection = connection
        self.pid = os.getpid()
        self.opened_at = self.last_used = time.monotonic()
        self.sent = 0


def _sessions():
    """Return the current thread's sessions, creating the dict on first use."""
    if not hasattr(_local, "sessions"):
        _local.sessions = {}
    return _local.sessions


def _close_quietly(connection):
    """Close an SMTP connection politely if possible, forcibly otherwise. Never raises."""
    try:
        connection.quit()
    except (OSError, smtplib.SMTPException):
        connection.close()


class PooledSMTPEmailBackend(EmailBackend):
    """Django SMTP backend that reuses one SMTP session per process and thread."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reused = False

    @property
    def _key(self):
        """Identify the relay and login this backend talks to, so unlike backends never share a session."""
        return (
            self.host, self.port, self.username, self.password,
            self.use_tls, self.use_ssl, self.timeout, self.ssl_keyfile, self.ssl_certfile,
        )

    def _recycle_reason(self, session):
        """Return why ``session`` must not be used again, or None if it is still good."""
        now = time.monotonic()
        if session.pid != os.getpid():
            return "inherited through fork"
        if now - session.last_used > getattr(settings, "EOX_NELP_SMTP_POOL_MAX_IDLE_SECONDS", 5):
            return "idle too long"
        if session.sent >= getattr(settings, "EOX_NELP_SMTP_POOL_MAX_MESSAGES", 100):
            return "message limit reached"
        if now - session.opened_at > getattr(settings, "EOX_NELP_SMTP_POOL_MAX_AGE_SECONDS", 300):
            return "too old"
        return None

    def _discard(self, reason):
        """Really close this backend's session and forget it."""
        session = _sessions().pop(self._key, None)
        self.connection = None
        if session:
            logger.debug("Dropping pooled SMTP session to %s:%s (%s).", self.host, self.port, reason)
            # A session created before fork() shares its socket with the parent: sending QUIT on it
            # would end the parent's session, so the child just lets go of its copy.
            if session.pid == os.getpid():
                _close_quietly(session.connection)

    def open(self):
        """Reuse this thread's live session or open a new one. Same return contract as the stock backend."""
        if self.connection:
            return False

        session = _sessions().get(self._key)
        if session:
            reason = self._recycle_reason(session)
            if reason is None:
                self.connection, self._reused = session.connection, True
                return False
            self._discard(reason)

        self._reused = False
        opened = super().open()
        if opened:
            _sessions()[self._key] = _Session(self.connection)
        return opened

    def close(self):
        """Hand the session back to the pool instead of closing it (errors close it, see ``_send``)."""
        self.connection = None

    def _send(self, email_message):
        """Send one message on the pooled session, closing the session if anything goes wrong."""
        session = _sessions().get(self._key)
        if self.connection and session and (reason := self._recycle_reason(session)):
            # A long ``send_messages`` batch can outlive the limits; check before every message.
            self._discard(reason)
            if not self.open():  # connect failure under fail_silently, as in the stock backend
                return False

        # The stock ``_send`` swallows SMTP errors under fail_silently; we need to see them to
        # decide whether the session died, so we apply fail_silently ourselves below.
        fail_silently, self.fail_silently = self.fail_silently, False
        try:
            sent = self._send_retrying_dropped_session(email_message, fail_silently)
        except Exception as error:
            self._discard(f"send failed: {type(error).__name__}")
            if fail_silently and isinstance(error, smtplib.SMTPException):
                return False
            raise
        finally:
            self.fail_silently = fail_silently

        if sent and (session := _sessions().get(self._key)):
            session.sent += 1
            session.last_used = time.monotonic()
        return sent

    def _send_retrying_dropped_session(self, email_message, fail_silently):
        """Stock send; if the server dropped a *reused* session, send once more on a fresh one."""
        try:
            return super()._send(email_message)
        except SESSION_DROPPED:
            if not self._reused:
                raise
        self._discard("dropped by server")
        self.fail_silently = fail_silently  # a failed reconnect follows the caller's choice, like any first connect
        if not self.open():
            return False
        self.fail_silently = False
        return super()._send(email_message)
