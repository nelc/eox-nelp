"""This file contains all the test for the initialized_events.py file.

Classes:
    InitializedCourseTransformerTestCase: Tests cases for InitializedCourseTransformer class.
"""
from django.test import TestCase
from tincan import LanguageMap

from eox_nelp.edxapp_wrapper.event_routing_backends import constants
from eox_nelp.processors.tests.xapi.mixins import BaseCourseObjectTestCaseMixin
from eox_nelp.processors.xapi.event_transformers import InitializedCourseTransformer


class InitializedCourseTransformerTestCase(BaseCourseObjectTestCaseMixin, TestCase):
    """Test class for InitializedCourseTransformer class."""
    transformer_class = InitializedCourseTransformer

    def test_verb_attribute(self):
        """ Test case that checks that the _verb attribute has the right values.

        Expected behavior:
            - Verb id is the expected value.
            - Verb display is the expected value.
        """
        verb = self.transformer_class._verb  # pylint: disable=protected-access

        self.assertEqual(constants.XAPI_VERB_INITIALIZED, verb.id)
        self.assertEqual(LanguageMap({constants.EN: constants.INITIALIZED}), verb.display)
