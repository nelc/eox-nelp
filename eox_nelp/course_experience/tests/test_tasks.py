"""Unit tests for course_experience.tasks.

Validates mapping from kind to model and the update_or_create call
behaviour for both Course and Unit kinds, and ensures unknown kinds are logged.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from eox_nelp.course_experience import tasks


class TestPersistExperienceToDB:
    """Test the persist_experience_to_db task for correct model mapping and update_or_create behaviour."""
    def setup_method(self):
        """Setup common test data."""
        # pylint: disable=attribute-defined-outside-init
        self.user_id = 7
        self.target_id = "course-xyz"
        # include course_id in payload to exercise pop/assignment logic
        self.value = {"course_id": "course-1", "comment": "ok"}
        # minimal fake model with objects.update_or_create spy
        self.fake_model = SimpleNamespace(objects=MagicMock())

    @patch("eox_nelp.course_experience.tasks.FeedbackCourse")
    def test_persist_course_kind_calls_update_or_create(self, mock_model):
        """Test that FeedbackCourse kind results in update_or_create call with course_id_id."""
        mock_model.return_value = self.fake_model
        # patch the class reference to our fake model object
        # call with a copy because function mutates the dict passed in
        tasks.persist_experience_to_db("FeedbackCourse", self.user_id, self.target_id, self.value.copy())

        expected_defaults = {"course_id_id": "course-1", "comment": "ok"}
        mock_model.objects.update_or_create.assert_called_once_with(
            defaults=expected_defaults, author_id=self.user_id, course_id_id=self.target_id
        )

    @patch("eox_nelp.course_experience.tasks.LikeDislikeUnit")
    def test_persist_unit_kind_calls_update_or_create_with_item_id(self, mock_model):
        """Test that LikeDislikeUnit kind results in update_or_create call with item_id."""
        mock_model.return_value = self.fake_model
        kind = "LikeDislikeUnit"
        target_item = "item-123"
        value = {"course_id": "course-1", "score": 1}

        tasks.persist_experience_to_db(kind, self.user_id, target_item, value.copy())

        expected_defaults = {"course_id_id": "course-1", "score": 1}
        mock_model.objects.update_or_create.assert_called_once_with(
            defaults=expected_defaults, author_id=self.user_id, item_id=target_item
        )

    @patch("eox_nelp.course_experience.tasks.logger")
    def test_unknown_kind_logs_warning_and_returns(self, mock_logger):
        """Test that an unknown kind results in a warning log and no database call."""
        tasks.persist_experience_to_db("NonExistingKind", 1, "t", {})

        mock_logger.warning.assert_called_once()
