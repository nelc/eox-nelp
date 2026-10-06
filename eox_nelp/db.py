"""Database router to route read queries to a read replica database."""
import threading

from django.conf import settings
from django.core.signals import request_finished, request_started

# Per-thread "this unit of work has written a routed model" flag. A unit of work is one request or one
# Celery task; the flag is cleared at both ends of each so it never leaks into the next one on a reused thread.
_state = threading.local()


def reset_read_your_writes(*args, **kwargs):  # pylint: disable=unused-argument
    """Forget any write recorded for the current thread."""
    _state.wrote = False


request_started.connect(reset_read_your_writes, dispatch_uid="eox_nelp_db_reset_on_request_started")
request_finished.connect(reset_read_your_writes, dispatch_uid="eox_nelp_db_reset_on_request_finished")

try:
    from celery.signals import task_postrun, task_prerun
except ImportError:  # pragma: no cover - celery is always installed with edx-platform
    pass
else:
    task_prerun.connect(reset_read_your_writes, dispatch_uid="eox_nelp_db_reset_on_task_prerun", weak=False)
    task_postrun.connect(reset_read_your_writes, dispatch_uid="eox_nelp_db_reset_on_task_postrun", weak=False)


class AppLabelReadReplicaRouter:
    """
    A database router that directs read operations for specified apps to a read replica database.
    The apps to route can be configured via the 'READ_REPLICA_APPS_LABELS_FORCED' setting.
    https://docs.djangoproject.com/en/5.0/topics/db/multi-db/#using-routers

    Read-your-writes: once the current request or task writes a model of a routed app, later reads of
    routed apps in that same request/task go to the primary. Replication lag would otherwise make a row
    that was just written invisible, e.g. platform_plugin_aspects re-reading a CourseEnrollment in its
    on_commit hook raised DoesNotExist and turned successful enrollments into 500s.
    """

    route_app_labels = getattr(settings, "READ_REPLICA_APPS_LABELS_FORCED", [])

    def db_for_read(self, model, **hints):  # pylint: disable=unused-argument
        """
        Only handles reading. If the app matches, use the replica unless this request/task already wrote.
        """
        # pylint: disable=protected-access
        if model._meta.app_label in self.route_app_labels and "read_replica" in settings.DATABASES:
            return "default" if getattr(_state, "wrote", False) else "read_replica"
        return None

    def db_for_write(self, model, **hints):  # pylint: disable=unused-argument
        """
        Record that a routed app was written, then let the default routing pick the database.
        """
        # pylint: disable=protected-access
        if model._meta.app_label in self.route_app_labels:
            _state.wrote = True
