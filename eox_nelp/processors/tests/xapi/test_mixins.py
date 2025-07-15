"""This file contains all the tests for the mixins.py file.

Classes:
    BaseCourseObjectTransformerMixinTestCase: Test class for BaseCourseObjectTransformerMixin class.
    BaseModuleObjectTransformerMixinTestCase: Test class for BaseModuleObjectTransformerMixin class.
"""
from django.test import TestCase

from eox_nelp.processors.xapi.mixins import BaseCourseObjectTransformerMixin, BaseModuleObjectTransformerMixin


class BaseCourseObjectTransformerMixinTestCase(TestCase):
    """Test class for BaseCourseObjectTransformerMixin class."""

    def test_course_id_not_set(self):
        """ Test case that checks that the exception NotImplementedError is raised
        when the course_id property has not been overridden.

        Expected behavior:
            - NotImplementedError exception is raised
        """
        mixin = BaseCourseObjectTransformerMixin()

        with self.assertRaises(NotImplementedError):
            mixin.course_id  # pylint: disable=pointless-statement

    def test_get_context_activities(self):
        """ Test that the method get_context_activities returns None

        Expected behavior:
            - None value is returned
        """
        mixin = BaseCourseObjectTransformerMixin()

        self.assertIsNone(mixin.get_context_activities())


class BaseModuleObjectTransformerMixinTestCase(TestCase):
    """Test class for BaseModuleObjectTransformerMixin class."""

    def test_course_id_not_set(self):
        """ Test case that checks that the exception NotImplementedError is raised
        when the course_id property has not been overridden.

        Expected behavior:
            - NotImplementedError exception is raised
        """
        mixin = BaseModuleObjectTransformerMixin()

        with self.assertRaises(NotImplementedError):
            mixin.course_id  # pylint: disable=pointless-statement

    def test_item_id_not_set(self):
        """ Test case that checks that the exception NotImplementedError is raised
        when the item_id property has not been overridden.

        Expected behavior:
            - NotImplementedError exception is raised
        """
        mixin = BaseModuleObjectTransformerMixin()

        with self.assertRaises(NotImplementedError):
            mixin.item_id  # pylint: disable=pointless-statement
