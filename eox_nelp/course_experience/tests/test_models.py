"""This file contains all the test for models.py file.

Classes:
    FeedbackCourseTestCase: Test FeedbackCourse model.
    FeedbackUnitTestCase: Test FeedbackUnit model.
"""
import unittest

from django.contrib.auth import get_user_model
from mock import patch

from eox_nelp.course_experience.models import FeedbackCourse, FeedbackUnit
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview

User = get_user_model()


class BaseFeedbackTestCase:
    """Base class for feedback models."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup common conditions for every test case"""
        self.author, _ = User.objects.get_or_create(
            username="fake-user",
            email="fake@example.com",
        )
        self.course, _ = CourseOverview.objects.get_or_create(id="course-v1:test+Cx108+2024_T4")

    @patch("eox_nelp.course_experience.models.tracker")
    def test_event_is_emitted(self, tracker_mock):
        """
        Tests that the feedback event is emmitted when an instance model is saved

        Expected behavior:
            - emit method is called with the right data.
        """
        expected_event_data = {
            key: str(value)
            for key, value in self.instance_data.items()  # pylint: disable=no-member
        }
        expected_event_data["author"] = str(self.author.id)
        instance = self.test_class(**self.instance_data)  # pylint: disable=no-member

        instance.save()

        tracker_mock.emit.assert_called_once_with(
            self.event_name,  # pylint: disable=no-member
            expected_event_data,
        )


class FeedbackCourseTestCase(BaseFeedbackTestCase, unittest.TestCase):
    """Test class for FeedbackCourse model. """

    def setUp(self):
        """Setup common conditions for every test case"""
        super().setUp()
        self.test_class = FeedbackCourse
        self.instance_data = {
            "author": self.author,
            "rating_content": 5,
            "feedback": "This is a great course",
            "public": False,
            "course_id": self.course,
            "rating_instructors": 4,
            "recommended": True,
        }
        self.event_name = "nelc.eox_nelp.course_experience.feedback_course"


class FeedbackUnitTestCase(BaseFeedbackTestCase, unittest.TestCase):
    """Test class for FeedbackUnit model. """

    def setUp(self):
        """Setup common conditions for every test case"""
        super().setUp()
        self.test_class = FeedbackUnit
        self.instance_data = {
            "author": self.author,
            "rating_content": 5,
            "feedback": "This is a great unit",
            "public": False,
            "course_id": self.course,
            "item_id": "block-v1:edX+cd1011+2024t1+type@vertical+block@base_item"
        }
        self.event_name = "nelc.eox_nelp.course_experience.feedback_unit"
