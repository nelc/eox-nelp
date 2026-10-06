"""Tests for the read replica database router."""
from unittest.mock import patch

from celery.signals import task_postrun, task_prerun
from django.contrib.auth.models import Permission, User
from django.core.signals import request_finished, request_started
from django.test import TestCase, override_settings

from eox_nelp import db
from eox_nelp.db import AppLabelReadReplicaRouter

DATABASES_WITH_REPLICA = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"},
    "read_replica": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"},
}


@override_settings(DATABASES=DATABASES_WITH_REPLICA)
@patch.object(AppLabelReadReplicaRouter, "route_app_labels", ["auth"])
class AppLabelReadReplicaRouterTestCase(TestCase):
    """AppLabelReadReplicaRouter tests. `auth` stands in for the routed apps (student, user, ...)."""

    def setUp(self):
        """Start every test as a fresh unit of work."""
        self.router = AppLabelReadReplicaRouter()
        db.reset_read_your_writes()

    def test_routed_app_reads_from_replica(self):
        """Reads of a routed app go to the replica by default."""
        self.assertEqual(self.router.db_for_read(User), "read_replica")

    def test_not_routed_app_is_left_to_other_routers(self):
        """Apps outside READ_REPLICA_APPS_LABELS_FORCED are not decided here."""
        with patch.object(AppLabelReadReplicaRouter, "route_app_labels", ["student"]):
            self.assertIsNone(self.router.db_for_read(User))

    def test_reads_after_a_routed_write_go_to_primary(self):
        """The row just written is read back from the primary, not from a lagging replica."""
        self.assertIsNone(self.router.db_for_write(User))

        self.assertEqual(self.router.db_for_read(User), "default")
        self.assertEqual(self.router.db_for_read(Permission), "default")

    def test_write_to_not_routed_app_keeps_replica(self):
        """Only writes to routed apps switch reads to the primary."""
        with patch.object(AppLabelReadReplicaRouter, "route_app_labels", ["student"]):
            self.router.db_for_write(User)
        self.assertEqual(self.router.db_for_read(User), "read_replica")

    def test_flag_is_cleared_at_request_and_task_boundaries(self):
        """A write must not send the next request or task on the same thread to the primary."""
        for signal in (request_started, request_finished, task_prerun, task_postrun):
            self.router.db_for_write(User)
            signal.send(sender=None)
            self.assertEqual(self.router.db_for_read(User), "read_replica", signal)

    def test_no_replica_configured(self):
        """Without a read_replica database the router stays out of the way."""
        with override_settings(DATABASES={"default": DATABASES_WITH_REPLICA["default"]}):
            self.assertIsNone(self.router.db_for_read(User))
