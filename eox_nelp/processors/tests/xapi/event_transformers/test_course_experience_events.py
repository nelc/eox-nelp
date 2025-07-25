"""This file contains all the test for the course_experience_events.py file.

Classes:
    FeedBackCourseTransformerTestCase: Tests cases for FeedBackCourseTransformer class.
    FeedBackUnitTransformerTestCase: Tests cases for FeedBackUnitTransformer class.
"""
from django.test import TestCase
from mock import call
from tincan import LanguageMap, Result

from eox_nelp.edxapp_wrapper.event_routing_backends import constants
from eox_nelp.processors.tests.xapi.mixins import BaseCourseObjectTestCaseMixin, BaseModuleObjectTestCaseMixin
from eox_nelp.processors.xapi import constants as eox_nelp_constants
from eox_nelp.processors.xapi.event_transformers import FeedBackCourseTransformer, FeedBackUnitTransformer


class BaseFeedBackTransformerTestCase:
    """Base class that contains all the common feedback test cases"""

    def test_verb_attribute(self):
        """ Test case that checks that the _verb attribute has the right values.

        Expected behavior:
            - Verb id is the expected value.
            - Verb display is the expected value.
        """
        verb = self.transformer_class._verb  # pylint: disable=protected-access,no-member

        # pylint: disable=no-member
        self.assertEqual(eox_nelp_constants.XAPI_VERB_RATED, verb.id)
        self.assertEqual(LanguageMap({constants.EN: eox_nelp_constants.RATED}), verb.display)

    def test_get_result_method(self):
        """Test case that checks that the course_id property has been overridden and returns the expected value.

        Expected behavior:
            - result is the expected value.
            - get_data has been called twice with the right parameters.
        """
        rating_content = "4"
        feedback = "This is a great activity"
        min_score = eox_nelp_constants.MIN_FEEDBACK_SCORE
        max_score = eox_nelp_constants.MAX_FEEDBACK_SCORE
        self.transformer_class.get_data.side_effect = [rating_content, feedback]  # pylint: disable=no-member
        transformer = self.transformer_class()  # pylint: disable=no-member
        expected_result = Result(
            score={
                "scaled": int(rating_content) / max_score,
                "raw": int(rating_content),
                "min": min_score,
                "max": max_score,
            },
            response=feedback,
        )

        result = transformer.get_result()

        # pylint: disable=no-member
        self.assertEqual(expected_result, result)
        self.assertEqual(
            [call("data.rating_content"), call("data.feedback")],
            self.transformer_class.get_data.call_args_list,
        )


class FeedBackCourseTransformerTestCase(BaseCourseObjectTestCaseMixin, BaseFeedBackTransformerTestCase, TestCase):
    """Test class for FeedBackCourseTransformer class."""
    transformer_class = FeedBackCourseTransformer


class FeedBackUnitTransformerTestCase(BaseModuleObjectTestCaseMixin, BaseFeedBackTransformerTestCase, TestCase):
    """Test class for FeedBackUnitTransformer class."""
    transformer_class = FeedBackUnitTransformer

    def test_item_id_property(self):
        """Test case that checks that the item_id property has been overridden and returns the expected value.

        Expected behavior:
            - item_id is the expected value.
            - get_data has been called with the right parameters.
        """
        item_id = "block-v1:edx+CS104+2023+type@vertical+block@cbf124449a7a46cd82270b6051d6e902"
        self.transformer_class.get_data.return_value = item_id
        transformer = self.transformer_class()

        self.assertEqual(item_id, transformer.item_id)
        self.transformer_class.get_data.assert_called_once_with("data.item_id", required=True)
