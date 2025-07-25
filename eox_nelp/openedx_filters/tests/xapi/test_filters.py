"""This file contains all the test for the filters.py file.

Classes:
    XApiActorFilterTestCase: Tests cases for XApiActorFilter filter class.
    XApiCourseObjectFilterTestCase: Test cases for XApiCourseObjectFilter filter class.
    XApiXblockObjectFilterTestCase: Test cases for XApiXblockObjectFilter filter class.
    XApiVerbFilterTestCase: Test cases for XApiVerbFilter filter class.
    XApiContextFilterTestCase: Test cases for XApiContextFilter filter class.
    XApiCertificateContextFilterTestCase: Test cases for XApiCertificateContextFilter filter class.
"""
import json

from ddt import data, ddt, unpack
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey
from tincan import Activity, ActivityDefinition, Agent, Context, Extensions, LanguageMap, Verb

from eox_nelp.edxapp_wrapper.event_routing_backends import constants
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.openedx_filters.xapi.filters import (
    XApiActorFilter,
    XApiCertificateContextFilter,
    XApiContextFilter,
    XApiCourseObjectFilter,
    XApiVerbFilter,
    XApiXblockObjectFilter,
)
from eox_nelp.processors.xapi.constants import DEFAULT_LANGUAGE

User = get_user_model()


class XApiActorFilterTestCase(TestCase):
    """Test class for XApiActorFilter filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.filter = XApiActorFilter(
            filter_type="event_routing_backends.processors.xapi.transformer.xapi_transformer.get_actor",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiActorFilter"],
        )
        self.username = "xapi"
        self.email = "xapi@example.com"
        User.objects.update_or_create(username=self.username, email=self.email)

    def test_user_does_not_exist(self):
        """ Test case when the user is not found by the email.

        Expected behavior:
            - Returned value is the same as the given value.
        """
        email = "invalid-email@example.com"
        actor = Agent(
            mbox=email,
        )

        actor = self.filter.run_filter(transformer=Mock(), result=actor)["result"]

        self.assertEqual(f"mailto:{email}", actor.mbox)

    def test_invalid_configuration(self):
        """ Test case when the actor agent doesn't have the attribute mbox,
        this case happens when the XAPI_AGENT_IFI_TYPE setting is different from mbox.

        Expected behavior:
            - Raises TypeError exception.
        """
        actor = Agent(
            account={"homePage": "https://example.com", "name": "harry-potter"}
        )

        self.assertRaises(TypeError, self.filter.run_filter, actor)

    def test_update_given_actor(self):
        """ Test case when the result is updated with the username.

        Expected behavior:
            - Returned value contains right mbox value.
            - Returned value contains right name value.
        """
        actor = Agent(
            mbox=self.email,
        )

        actor = self.filter.run_filter(transformer=Mock(), result=actor)["result"]

        self.assertEqual(f"mailto:{self.email}", actor.mbox)
        self.assertEqual(self.username, actor.name)


class XApiCourseObjectFilterTestCase(TestCase):
    """Test class for XApiCourseObjectFilter filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.filter = XApiCourseObjectFilter(
            filter_type="event_routing_backends.processors.xapi.enrollment_events.base_enrollment.get_object",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiCourseObjectFilter"],
        )

    def test_course_id_not_found(self):
        """ Test case when the course_id cannot be extracted from the Activity id.

        Expected behavior:
            - Returned value is the same as the given value.
        """
        activity = Activity(
            id="https://example.com/course/course-v1-invalid-edx+CS105+2023-T3",
            definition=ActivityDefinition(
                type=constants.XAPI_ACTIVITY_COURSE,
            ),
        )

        returned_activity = self.filter.run_filter(transformer=Mock(), result=activity)["result"]

        self.assertEqual(activity, returned_activity)

    def test_invalid_type(self):
        """ Test case when the type is different from http://adlnet.gov/expapi/activities/course.

        Expected behavior:
            - Returned value is the same as the given value.
        """
        activity = Activity(
            id="https://example.com/course/course-v1:edx+CS105+2023-T3",
            definition=ActivityDefinition(
                type="another-type",
            ),
        )

        returned_activity = self.filter.run_filter(transformer=Mock(), result=activity)["result"]

        self.assertEqual(activity, returned_activity)

    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_update_result(self, get_course_mock):
        """ Test case when name and description are updated.

        Expected behavior:
            - Definition name has been updated.
            - Definition description has been updated.
            - get_course_from_id was called with the right parameter.
        """
        course = {
            "display_name": "new-course-name",
            "language": "ar",
            "short_description": "This is a short description",
        }

        get_course_mock.return_value = course
        activity = Activity(
            id="https://example.com/course/course-v1:edx+CS105+2023-T3",
            definition=ActivityDefinition(
                type=constants.XAPI_ACTIVITY_COURSE,
                name=LanguageMap(en="old-course-name"),
            ),
        )

        returned_activity = self.filter.run_filter(transformer=Mock(), result=activity)["result"]

        self.assertEqual({course['language']: course["display_name"]}, returned_activity.definition.name)
        self.assertEqual({course['language']: course["short_description"]}, returned_activity.definition.description)
        get_course_mock.assert_called_once_with("course-v1:edx+CS105+2023-T3")

    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_invalid_language(self, get_course_mock):
        """ Test case when language has not been set.

        Expected behavior:
            - Definition name has been updated with default language.
            - Definition description has been updated with default language.
            - get_course_from_id was called with the right parameter.
        """
        course = {
            "display_name": "new-course-name",
            "language": None,
            "short_description": "This is a short description",
        }

        get_course_mock.return_value = course
        activity = Activity(
            id="https://example.com/course/course-v1:edx+CS105+2023-T3",
            definition=ActivityDefinition(
                type=constants.XAPI_ACTIVITY_COURSE,
                name=LanguageMap(en="old-course-name"),
            ),
        )

        returned_activity = self.filter.run_filter(transformer=Mock(), result=activity)["result"]

        self.assertEqual({DEFAULT_LANGUAGE: course["display_name"]}, returned_activity.definition.name)
        self.assertEqual({DEFAULT_LANGUAGE: course["short_description"]}, returned_activity.definition.description)
        get_course_mock.assert_called_once_with("course-v1:edx+CS105+2023-T3")


@ddt
class XApiXblockObjectFilterTestCase(TestCase):
    """Test class for XApiXblockObjectFilterr filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.default_values = {
            "data.problem_id": "block-v1:edx+CS105+2023-T3+type@problem+block@0221040b086c4618b6b2b2a554558",
            "course_id": "course-v1:edx+CS105+2023-T3",
        }
        self.filter = XApiXblockObjectFilter(
            filter_type="event_routing_backends.processors.xapi.problem_interaction_events.base_problems.get_object",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiXblockObjectFilter"],
        )
        self.transformer = Mock()
        self.transformer.event = {"name": "edx.grades.problem.submitted"}
        self.transformer.get_data.side_effect = lambda x: self.default_values[x]
        self.transformer._get_submission.return_value = {}  # pylint: disable=protected-access
        self.course = {"language": "ar"}
        self.activity = None

        self.item = Mock()
        self.item.markdown = ""
        self.item.display_name = "testing-course"
        modulestore.return_value.get_item.return_value = self.item

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()
        self.transformer.reset_mock()

    def set_activity(self, definition_type):
        """Set the activity argument for the given type"""
        self.activity = Activity(
            id="https://example.com/xblock/block-v1:edx+CS105+2023-T3+type@problem+block@0221040b086c4618b6b2b2a554558",
            definition=ActivityDefinition(
                type=definition_type,
                name=LanguageMap(en="old-testing-course"),
            )
        )

    @data(
        (constants.XAPI_ACTIVITY_MODULE, None),
        (constants.XAPI_ACTIVITY_MODULE, ""),
        (constants.XAPI_ACTIVITY_QUESTION, None),
        (constants.XAPI_ACTIVITY_QUESTION, ""),
    )
    @unpack
    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_invalid_display_name(self, definition_type, display_name, get_course_mock):
        """ Test case when display_name is None or an empty string.

        Expected behavior:
            - Definition name wasn't updated.
        """
        course_name = "testing-course"
        get_course_mock.return_value = self.course
        self.set_activity(definition_type)

        # Set results of get_data method.
        self.item.display_name = display_name
        self.transformer.get_data.side_effect = lambda x: self.default_values[x]

        # Set input arguments.
        self.activity.definition.name = LanguageMap({DEFAULT_LANGUAGE: course_name})

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=self.activity)["result"]

        self.assertEqual({DEFAULT_LANGUAGE: course_name}, returned_activity.definition.name)

    @data(constants.XAPI_ACTIVITY_MODULE, constants.XAPI_ACTIVITY_QUESTION)
    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_valid_display_name(self, definition_type, get_course_mock):
        """ Test case when display_name is found and valid.

        Expected behavior:
            - Definition name has been updated.
        """
        get_course_mock.return_value = self.course
        self.set_activity(definition_type)

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=self.activity)["result"]

        self.assertEqual(
            {self.course['language']: self.item.display_name},
            returned_activity.definition.name,
        )

    @data(constants.XAPI_ACTIVITY_MODULE, constants.XAPI_ACTIVITY_QUESTION)
    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_update_description(self, definition_type, get_course_mock):
        """ Test case when item label is valid and the description is updated.

        Expected behavior:
            - Definition description has been updated.
        """
        item = Mock()
        label = "This is a great label"
        item.markdown = f">>{label}<<"
        item.display_name = None
        modulestore.return_value.get_item.return_value = item
        get_course_mock.return_value = self.course
        self.set_activity(definition_type)

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=self.activity)["result"]

        self.assertEqual(
            {self.course['language']: label},
            returned_activity.definition.description,
        )

    @data(constants.XAPI_ACTIVITY_MODULE, constants.XAPI_ACTIVITY_QUESTION)
    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_empty_label(self, definition_type, get_course_mock):
        """ Test case when the item markdown doesn't contain a label.

        Expected behavior:
            - Definition description is an empty dict.
        """
        get_course_mock.return_value = self.course
        self.set_activity(definition_type)

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=self.activity)["result"]

        self.assertEqual({}, returned_activity.definition.description)

    @data(constants.XAPI_ACTIVITY_MODULE, constants.XAPI_ACTIVITY_QUESTION)
    @patch("eox_nelp.openedx_filters.xapi.filters.get_course_from_id")
    def test_default_language(self, definition_type, get_course_mock):
        """ Test case when the course has no language or is not valid.

        Expected behavior:
            - Definition name has the default key language.
        """
        get_course_mock.return_value = {}
        self.set_activity(definition_type)

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=self.activity)["result"]

        self.assertEqual([DEFAULT_LANGUAGE], list(returned_activity.definition.name.keys()))

    def test_invalid_event(self):
        """ Test case when the event definition type is different from http://adlnet.gov/expapi/activities/module
        or http://adlnet.gov/expapi/activities/question.

        Expected behavior:
            - Returned activity is the same input activity.
        """
        self.transformer.event = {"name": "other-event"}
        activity = Activity(
            id="empty-activity",
            definition=ActivityDefinition(
                type="invalid-type",
            )
        )

        returned_activity = self.filter.run_filter(transformer=self.transformer, result=activity)["result"]

        self.assertEqual(activity, returned_activity)


@ddt
class XApiVerbFilterTestCase(TestCase):
    """Test class for XApiVerbFilter filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.filter = XApiVerbFilter(
            filter_type="event_routing_backends.processors.xapi.transformer.xapi_transformer.get_verb",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiVerbFilter"],
        )

    def test_change_language(self):
        """ Test case when the verb display key is the open edx default value and must be changed

        Expected behavior:
            - Returned verb has the eox-nelp default language.
        """
        display = "any-word"
        verb = Verb(
            id='testing-id',
            display=LanguageMap({constants.EN: display})
        )

        verb = self.filter.run_filter(transformer=Mock(), result=verb)["result"]

        self.assertEqual(display, verb.display[DEFAULT_LANGUAGE])

    @data("fr", "ar", "de", "es")
    def test_keep_language(self, language):
        """ Test case when the verb display key is different from default value.

        Expected behavior:
            - Returned verb has not been modified.
        """
        display = "any-word"
        verb = Verb(
            id='testing-id',
            display=LanguageMap({language: display})
        )

        verb = self.filter.run_filter(transformer=Mock(), result=verb)["result"]

        self.assertEqual(display, verb.display[language])


@ddt
class XApiContextFilterTestCase(TestCase):
    """Test class for XApiContextFilter filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.filter = XApiContextFilter(
            filter_type="event_routing_backends.processors.xapi.transformer.xapi_transformer.get_context",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiContextFilter"],
        )

    def tearDown(self):
        """Clean cache and restarts mocks"""
        modulestore.reset_mock()

    @data(
        ("registration", "550e8400-e29b-41d4-a716-446655440000"),
        ("platform", "This is the platform name"),
        ("revision", "2024-10-25"),
        ("language", "en-US"),
    )
    @unpack
    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_update_string_attributes(self, attribute, value, extra_context_mock):
        """ This tests that arguments that must be strings has been updated after the filter execution.

        Expected behavior:
            - The attribute is equal to the expected value.
            - _get_extra_context was called with the right parameter.
        """
        context = Context()
        transformer = Mock()
        extra_context_mock.return_value = {attribute: value}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertEqual(value, str(getattr(context, attribute)))
        extra_context_mock.assert_called_once_with(transformer)

    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_update_instructor_attribute(self, extra_context_mock):
        """ This tests that the instructor attribute has been updated after the filter execution.

        Expected behavior:
            - The attribute is equal to the expected value.
            - _get_extra_context was called with the right parameter.
        """
        context = Context()
        transformer = Mock()
        expected_value = {"name": "Jhon", "mbox": "mailto:test@example.com"}
        extra_context_mock.return_value = {"instructor": expected_value}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        # Remove objectType key since that is a value that is added automatically by tincan
        result = json.loads(context.instructor.to_json())
        del result["objectType"]

        self.assertEqual(expected_value, result)
        extra_context_mock.assert_called_once_with(transformer)

    @data("instructor", "team")
    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_update_group_attributes(self, attribute, extra_context_mock):
        """ This tests attributes that can be set by a list of dictionaries, as the team or instructor attribute.

        Expected behavior:
            - The attribute is equal to the expected value.
            - _get_extra_context was called with the right parameter.
        """
        context = Context()
        transformer = Mock()
        expected_value = [
            {"name": "Jhon", "mbox": "mailto:test@example.com"},
            {"name": "Peter", "mbox": "mailto:peter@example.com"},
            {"name": "Alex", "mbox": "mailto:alex@example.com"},
        ]
        extra_context_mock.return_value = {attribute: expected_value}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        result = json.loads(getattr(context, attribute).member.to_json())

        # Remove objectType key since that is a value that is added automatically by tincan
        for member in result:
            del member["objectType"]

        self.assertEqual(expected_value, result)
        extra_context_mock.assert_called_once_with(transformer)

    @data("instructor", "team")
    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_raise_invalid_group(self, attribute, extra_context_mock):
        """This tests that the ValueError exception is raised when an invalid value is
        attempted to be associated with a group attribute.

        Expected behavior:
            - ValueError is raised.
            - _get_extra_context was called with the right parameter.
        """
        context = Context()
        transformer = Mock()
        invalid_value = "invalid-value"
        extra_context_mock.return_value = {attribute: invalid_value}

        self.assertRaises(ValueError, self.filter.run_filter, transformer, context)
        extra_context_mock.assert_called_once_with(transformer)

    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_update_extensions_attribute(self, extra_context_mock):
        """ This tests that the extensions attribute has been updated after the filter execution.

        Expected behavior:
            - The attribute is equal to the expected value.
            - _get_extra_contex was called with the right parameter.
        """
        context = Context()
        transformer = Mock()
        initial_value = {
            "http://id.tincanapi.com/extension/browser-info": {
                "code_name": "Mozilla",
                "name": "Firefox",
                "version": "5.0"
            },
        }
        context.extensions = initial_value
        extra_value = {
            "https://nelc.gov.sa/extensions/platform": {
                "name": {
                    "ar-SA": "التقنيات المتقدمة للتدريب",
                    "en-US": "Leading Tech for Training",
                },
            },
        }
        extra_context_mock.return_value = {"extensions": extra_value}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        expected_value = {**initial_value, **extra_value}

        self.assertEqual(expected_value, context.extensions)
        extra_context_mock.assert_called_once_with(transformer)

    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_invalid_attribute(self, extra_context_mock):
        """ This tests that the attribute has not been set when the context doesn't have the target attribute.

        Expected behavior:
            - Context doesn't have the attribute.
            - _get_extra_contex was called with the right parameter.
        """
        context = Mock()
        transformer = Mock()
        del context.any_attribute
        extra_context_mock.return_value = {"any_attribute": "any_value"}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertFalse(hasattr(context, "any_attribute"))
        extra_context_mock.assert_called_once_with(transformer)

    @data("context_activities", "statement")
    @patch.object(XApiContextFilter, "_get_extra_context")
    def test_unsupported_attribute(self, attribute, extra_context_mock):
        """ This tests that unsupported attributes has not been updated.

        Expected behavior:
            - The attribute is different from the new value.
            - _get_extra_contex was called with the right parameter.
        """
        context = Mock()
        transformer = Mock()
        new_value = "any_value"
        extra_context_mock.return_value = {attribute: new_value}

        context = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertNotEqual(new_value, getattr(context, attribute))
        extra_context_mock.assert_called_once_with(transformer)

    def test_get_context_from_general_settings(self):
        """This checks that the method `_get_extra_context` returns the right value
        from the general settings.

        Expected behavior:
            - Returned value is the expected value.
        """
        expected_value = {
            "instructor": {
                "name": "Jhon",
                "mbox": "test@example.com"
            },
            "platform": "My-great-platform",
            "language": "ar-SA",
        }
        transformer = Mock()
        transformer.get_data.return_value = None

        with override_settings(XAPI_EXTRA_CONTEXT=expected_value):
            result = self.filter._get_extra_context(transformer)  # pylint: disable=protected-access

        self.assertEqual(expected_value, result)

    def test_get_context_from_course_settings(self):
        """This checks that the method `_get_extra_context` returns the right value
        from the other_course_settings, this also checks that the platform settings
        are overridden.

        Expected behavior:
            - Returned value is the expected value.
            - get_course is called with the course key.
        """
        platform_settings = {
            "instructor": {
                "name": "Jhon",
                "mbox": "test@example.com"
            },
            "platform": "My-great-platform",
            "language": "ar-SA",
        }
        course_settings = {
            "XAPI_EXTRA_CONTEXT": {
                "instructor": {
                    "name": "Peter",
                    "mbox": "peter@example.com"
                },
                "extensions": {
                    "https://example.com/extensions/platform": {
                        "name": {
                            "ar-SA": "التكنولوجيا الرائدة",
                            "en-US": "Leading Tech for Training",
                        },
                    },
                },
            },
        }
        course = Mock()
        transformer = Mock()
        course.other_course_settings = course_settings
        transformer.get_data.return_value = "course-v1:edx+CS105+2023-T3"
        modulestore.return_value.get_course.return_value = course

        with override_settings(XAPI_EXTRA_CONTEXT=platform_settings):
            result = self.filter._get_extra_context(transformer)  # pylint: disable=protected-access

        expected_value = {**platform_settings, **course_settings.get("XAPI_EXTRA_CONTEXT")}

        self.assertEqual(expected_value, result)
        modulestore.return_value.get_course.assert_called_once_with(
            CourseKey.from_string(transformer.get_data())
        )


class XApiCertificateContextFilterTestCase(TestCase):
    """Test class for XApiCertificateContextFilter filter class."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.filter = XApiCertificateContextFilter(
            filter_type="event_routing_backends.processors.xapi.transformer.xapi_transformer.get_context",
            running_pipeline=["eox_nelp.openedx_filters.xapi.filters.XApiCertificateContextFilter"],
        )

    def test_certificate_id_does_not_exist(self):
        """ Tests when the transformer doesn't have the certificate_id value.

        Expected behavior:
            - Returned value is the same as the given value.
            - get_data method was called with the right parameter
        """
        transformer = Mock()
        transformer.get_data.return_value = None
        context = Context()

        result = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertEqual(context, result)
        transformer.get_data.assert_called_once_with("data.certificate_id")

    def test_update_certificate_with_extension(self):
        """ Tests that the context extensions has been updated when the transformer returns a valid certificate_id.

        Expected behavior:
            - Returned value contains certificate url.
            - Returned value keeps the previos extension.
            - get_data method was called with the right parameter
            - get_object_iri method was called with the right parameters
        """
        transformer = Mock()
        certificate_id = "3b8a5421b73748eeba4fb07e6fe2ec6a"
        certificate_url = f"http://local.overhang.io:8000/certificates/{certificate_id}"
        transformer.get_data.return_value = certificate_id
        transformer.get_object_iri.return_value = certificate_url
        context = Context(
            extensions=Extensions({"custom-test-extension": "any-value"})
        )

        result = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertEqual(
            certificate_url,
            result.extensions["http://id.tincanapi.com/extension/jws-certificate-location"],
        )
        self.assertTrue("custom-test-extension" in result.extensions)
        transformer.get_data.assert_called_once_with("data.certificate_id")
        transformer.get_object_iri.assert_called_once_with("certificates", certificate_id)

    def test_update_certificate_without_extension(self):
        """ Tests that the context extensions has been created when the transformer returns a valid certificate_id.

        Expected behavior:
            - Returned value contains certificate url.
            - get_data method was called with the right parameter
            - get_object_iri method was called with the right parameters
        """
        transformer = Mock()
        certificate_id = "3b8a5421b73748eeba4fb07e6fe2ec6a"
        certificate_url = f"http://local.overhang.io:8000/certificates/{certificate_id}"
        transformer.get_data.return_value = certificate_id
        transformer.get_object_iri.return_value = certificate_url
        context = Context()

        result = self.filter.run_filter(transformer=transformer, result=context)["result"]

        self.assertEqual(
            certificate_url,
            result.extensions["http://id.tincanapi.com/extension/jws-certificate-location"],
        )
        transformer.get_data.assert_called_once_with("data.certificate_id")
        transformer.get_object_iri.assert_called_once_with("certificates", certificate_id)
