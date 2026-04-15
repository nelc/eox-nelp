"""Database router to route read queries to a read replica database."""

from django.conf import settings


class AppLabelReadReplicaRouter:
    """
    A database router that directs read operations for specified apps to a read replica database.
    The apps to route can be configured via the 'READ_REPLICA_APPS_LABELS_FORCED' setting.
    https://docs.djangoproject.com/en/5.0/topics/db/multi-db/#using-routers
    """

    route_app_labels = getattr(settings, "READ_REPLICA_APPS_LABELS_FORCED", [])

    def db_for_read(self, model, **hints):  # pylint: disable=unused-argument
        """
        Only handles reading. If the app matches, use the replica.
        """
        # pylint: disable=protected-access
        if model._meta.app_label in self.route_app_labels and "read_replica" in settings.DATABASES:
            return "read_replica"
        return None
