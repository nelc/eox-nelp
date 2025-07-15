"""This file contains all the test for the grade_events.py file.

Classes:
    SubsectionSubmittedTransformerTestCase: Tests cases for SubsectionSubmittedTransformer class.
"""
from django.test import TestCase
from mock import patch
from tincan import ActivityDefinition, Context, Extensions, LanguageMap, Result

from eox_nelp.edxapp_wrapper.event_routing_backends import constants, event_transformers
from eox_nelp.processors.xapi import constants as eox_nelp_constants
from eox_nelp.processors.xapi.event_transformers import SubsectionSubmittedTransformer


class SubsectionSubmittedTransformerTestCase(TestCase):
    """Test class for SubsectionSubmittedTransformer class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.default_values = {
            "data.block_id": "block-v1:test+CS501+2022_T4+type@sequential+block@a54730a9b89f420a8d0343dd581b447a",
            "data.earned": 15,
            "data.possible": 30,
            "data.percent": 50,
            "data.attempts": 40,
        }
        self.transformer = SubsectionSubmittedTransformer()
        self.transformer.get_data.side_effect = lambda x: self.default_values[x]

    def tearDown(self):
        """Restore mocks' state"""
        self.transformer.get_data.reset_mock()

    def test_verb_attribute(self):
        """ Test case that checks that the get_verb method returns right values.

        Expected behavior:
            - Verb id is the expected value.
            - Verb display is the expected value.
        """
        verb = self.transformer.get_verb()

        self.assertEqual(constants.XAPI_VERB_ATTEMPTED, verb.id)
        self.assertEqual(LanguageMap({eox_nelp_constants.DEFAULT_LANGUAGE: constants.ATTEMPTED}), verb.display)

    def test_get_object_id(self):
        """ Test case that checks that the get_object_id method returns the right value.

        Expected behavior:
            - result is the expected value.
        """
        result = self.transformer.get_object_id()

        self.assertEqual(self.default_values["data.block_id"], result)

    def test_get_object_definition(self):
        """ Test case that checks that the get_object_definition method returns the right value.

        Expected behavior:
            - result is the expected value.
        """
        expected_value = ActivityDefinition(
            type=eox_nelp_constants.XAPI_ACTIVITY_UNIT_TEST
        )

        result = self.transformer.get_object_definition()

        self.assertEqual(expected_value, result)

    def test_get_result(self):
        """ Test case that checks that the get_result method returns the right value.

        Expected behavior:
            - result is the expected value.
        """
        expected_value = Result(
            success=self.default_values["data.earned"] >= self.default_values["data.possible"],
            score={
                "min": 0,
                "max": self.default_values["data.possible"],
                "raw": self.default_values["data.earned"],
                "scaled": self.default_values["data.percent"],
            }
        )

        result = self.transformer.get_result()

        self.assertEqual(expected_value, result)

    def test_get_context_with_parent_extensions(self):
        """ Tests that the context extensions have been updated when the parent extensions context is not None.

        Expected behavior:
            - Returned value contains attempt extension and its value is the expected.
            - Returned context contains the parent values.
        """
        with patch.object(event_transformers.ProblemSubmittedTransformer, 'get_context') as parent_context:
            parent_context.return_value = Context(
                extensions=Extensions({"parent_extensions": "any-value"})
            )
            context = self.transformer.get_context()

        self.assertEqual(
            self.default_values["data.attempts"],
            context.extensions[constants.XAPI_ACTIVITY_ATTEMPT],
        )
        self.assertTrue("parent_extensions" in context.extensions)

    def test_get_context(self):
        """ Tests that the context extensions have been created when the parent extensions context is None.

        Expected behavior:
            - Returned value contains attempt extension and its value is the expected.
        """
        with patch.object(event_transformers.ProblemSubmittedTransformer, 'get_context') as parent_context:
            parent_context.return_value = Context()
            context = self.transformer.get_context()

        self.assertEqual(
            self.default_values["data.attempts"],
            context.extensions[constants.XAPI_ACTIVITY_ATTEMPT],
        )
