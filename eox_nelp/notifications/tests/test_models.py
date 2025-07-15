"""This file contains all the test for notifications/models.py file.

Classes:
    UpcomingCourseDueDateTestCase: Test UpcomingCourseDueDate django model.
"""
import unittest

import pytest
from django.utils import timezone
from mock import patch

from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview
from eox_nelp.notifications import models
from eox_nelp.notifications.models import UpcomingCourseDueDate


@pytest.mark.django_db
class UpcomingCourseDueDateTestCase(unittest.TestCase):
    """Test class for model UpcomingCourseDueDate"""
    @patch("eox_nelp.notifications.tasks.notify_upcoming_course_due_date_by_id")
    def test_send_notifications(self, notify_upcoming_course_due_date_by_id_mock):
        """Test that the notify method of UpcomingCourseDueDate
        call the task `notify_upcoming_course_due_date_by_id` and the
        correct logs progress message.

        Expected behavior:
            - Log progress message successfully.
            - notify_upcoming_course_due_date_by_id method was called.
        """
        instance, _ = UpcomingCourseDueDate.objects.get_or_create(  # pylint: disable=no-member
            course=CourseOverview.objects.create(id="course-v1:test+Cx105+2022_T4"),
            location_id="block-v1:test+CS501+2022_T4+type@sequential+block@a54730a9b89f420a8d0343dd581b447a",
            due_date=timezone.now(),
            notification_date=timezone.now(),
        )
        processing_log = f"Processing notification for UpcomingCourseDueDate with id {instance.id}"

        with self.assertLogs(models.__name__, level="INFO") as logs:
            instance.notify()

        self.assertEqual(logs.output, [f"INFO:{models.__name__}:{processing_log}"])
        notify_upcoming_course_due_date_by_id_mock.delay.assert_called_with(instance.id)
