"""This file contains all the test for the utils.py file.

Classes:
    ExtractCourseIdFromStringTestCase: Tests cases for the extract_course_id_from_string method.
    GetCourseFromIdTestCase: Tests cases for the get_course_from_id method.
    NormalizeNationalIdTestCase: Tests cases for the normalize_national_id method.
"""
from ddt import data, ddt
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.user_api import errors
from eox_nelp.utils import (
    camel_to_snake,
    extract_course_id_from_string,
    get_course_from_id,
    get_item_label,
    normalize_national_id,
    save_extrainfo,
)

User = get_user_model()


@ddt
class ExtractCourseIdFromStringTestCase(TestCase):
    """Test class for the extract_course_id_from_string method."""

    @data(
        "this is a long string",
        "hjsdgafhawsdbfhsdyafgbhjsdbf1784561553415534",
        "this is a similar string course-v1:77777554a45sd4a2ad42s45d",
        "https://example.com/course/course-v1edx+CS105+2023-T3"
    )
    def test_course_id_not_found(self, value):
        """ Test that the method returns an empty string when any course_id is not found

        Expected behavior:
            - Returned value is an empty string
        """
        result = extract_course_id_from_string(value)

        self.assertEqual("", result)

    @data(
        ["course-v1:edx+PS874+2023-T3", "this is a course-v1:edx+PS874+2023-T3/) long string"],
        ["course-v1:edunext+CS105+2019-P3", "hjsdgafhawsdbfhgbhjsdbf1784561553415534course-v1:edunext+CS105+2019-P3"],
        ["course-v1:NELC+TR675+2022-K3", "this course-v1:NELC+TR675+2022-K3/ is a similar string course-v1:77775s45d"],
        ["course-v1:edx+CS105+2023-T3", "https://example.com/course/course-v1:edx+CS105+2023-T3"],
    )
    def test_course_id_found(self, value):
        """ Test that the method returns right course id.

        Expected behavior:
            - Returned value is the expected course id.
        """
        result = extract_course_id_from_string(value[1])

        self.assertEqual(value[0], result)

    def test_multiple_valid_ids(self):
        """ Test that the method returns the first value that matches the regular expression.

        Expected behavior:
            - Returned value is the expected course id.
        """
        string = (
            "/course-v1:edx+CS105+2023-T3/"
            "/course-v1:NELC+TR675+2022-K3/"
            "/course-v1:edx+PS874+2023-T3/"
            "/course-v1:edunext+CS105+2019-P3/"
        )

        result = extract_course_id_from_string(string)

        self.assertEqual("course-v1:edx+CS105+2023-T3", result)


class GetCourseFromIdTestCase(TestCase):
    """Test class for the get_course_from_id method."""

    @patch("eox_nelp.utils.get_course_overviews")
    def test_course_id_not_found(self, course_overviews_mock):
        """ Test that the method raises the right exception when there are no courses.

        Expected behavior:
            - Raises ValueError exception.
            - get_course_overviews method was called with the right parameter.
        """
        course_id = "course-v1:edx+CS105+2023-T3"
        course_overviews_mock.return_value = []

        self.assertRaises(ValueError, get_course_from_id, course_id)
        course_overviews_mock.assert_called_once_with([CourseKey.from_string(course_id)])

    @patch("eox_nelp.utils.get_course_overviews")
    def test_course_id_found(self, course_overviews_mock):
        """ Test that the method returns the expected value.

        Expected behavior:
            - Returned value is the expected course.
            - get_course_overviews method was called with the right parameter.
        """
        course_id = "course-v1:edx+CS105+2023-T3"
        expected_course = {"name": "test-course", "short_description": "This is a great course"}
        course_overviews_mock.return_value = [expected_course]

        course = get_course_from_id(course_id)

        self.assertEqual(expected_course, course)
        course_overviews_mock.assert_called_once_with([CourseKey.from_string(course_id)])


@ddt
class GetItemLabelTestCase(TestCase):
    """Test class for the get_item_lable method."""

    def test_item_does_not_have_markdown(self):
        """ Test when the item doesn't have any markdown attribute.

        Expected behavior:
            - Returns an empty string
        """
        fake_item = object()

        label = get_item_label(fake_item)

        self.assertEqual("", label)

    @data(None, 14, object)
    def test_invalid_markdown_type(self, markdown):
        """ Test when the markdown attribute is different from a string type.

        Expected behavior:
            - Returns an empty string
        """
        fake_item = Mock()
        fake_item.markdown = markdown

        label = get_item_label(fake_item)

        self.assertEqual("", label)

    def test_returns_label(self):
        """ Test that the method finds and returns the label for the given item.

        Expected behavior:
            - Returns expected label
        """
        expected_label = "This is a great label"
        markdown = f"""
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean eleifend odio elit. Etiam lacus quam,
            ultrices in ullamcorper a, ullamcorper eu ante. Nulla risus ante, congue sed tellus id, interdum accumsan
            purus. Nunc malesuada eget >>{expected_label}<< urna placerat gravida. Aliquam justo nunc, porttitor nec
            placerat non, gravida id arcu. Pellentesque condimentum sodales hendrerit.
        """
        fake_item = Mock()
        fake_item.markdown = markdown

        label = get_item_label(fake_item)

        self.assertEqual(expected_label, label)

    def test_returns_first_label(self):
        """ Test that the method returns the first label found.

        Expected behavior:
            - Returns expected label
        """
        expected_label = "This is a great label"
        wrong_label = "Wrong label"
        markdown = f"""
            Lorem ipsum dolor sit amet, >>{expected_label}<< consectetur adipiscing elit. Aenean eleifend odio elit.
            Etiam lacus quam, >>{wrong_label}<< ultrices in ullamcorper a, ullamcorper eu ante. Nulla risus ante,
            congue sed tellus id, interdum accumsan >>{wrong_label}<< purus. Nunc malesuada eget urna placerat
            gravida. Aliquam justo nunc, porttitor nec >>{wrong_label}<< placerat non, gravida id arcu.
            Pellentesque condimentum sodales hendrerit.
        """
        fake_item = Mock()
        fake_item.markdown = markdown

        label = get_item_label(fake_item)

        self.assertEqual(expected_label, label)

    def test_label_not_found(self):
        """ Test when the method doesn't find any labels.

        Expected behavior:
            - Returns an empty string
        """
        markdown = """
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean eleifend odio elit. Etiam lacus quam,
            ultrices in ullamcorper a, ullamcorper eu ante. Nulla risus ante, congue sed tellus id, interdum accumsan
            purus. Nunc malesuada eget urna placerat gravida. Aliquam justo nunc, porttitor nec
            placerat non, gravida id arcu. Pellentesque condimentum sodales hendrerit.
        """
        fake_item = Mock()
        fake_item.markdown = markdown

        label = get_item_label(fake_item)

        self.assertEqual("", label)


@ddt
class CamelToSnakeTestCase(TestCase):
    """Test class for the camel_to_snake method."""
    @data(
        ("CamelToSnake", "camel_to_snake"),
        ("This_isAMix", "this_is_a_mix"),
        ("not_camel_case", "not_camel_case"),
        ("ABGTET", "a_b_g_t_e_t"),
        ("58Yolo", "58_yolo"),
    )
    def test_camel_to_snake(self, test_data):
        """ Test right functionality.

        Expected behavior:
            - Returned value is the expected value.
        """
        input_value = test_data[0]
        expected_result = test_data[1]

        self.assertEqual(expected_result, camel_to_snake(input_value))

    @data(None, 14, object)
    def test_invalid_input(self, input_value):
        """ Test when the input is not a string.

        Expected behavior:
            - TypeError is raised
        """
        self.assertRaises(TypeError, camel_to_snake, input_value)


class SaveExtraInfoTestCase(TestCase):
    """Test class for the save_extrainfo method."""

    def test_save_extrainfo(self):
        """ Test right functionality.

        Expected behavior:
            - Extrainfo related objed has  the expected value.
        """
        user, _ = User.objects.get_or_create(username="vader1798")
        extrainfo_data = {
            "arabic_name": "أناكين سكاي ووكر",
            "is_phone_validated": True,
            "arabic_first_name": "أناكين",
            "arabic_last_name": "سكاي ووكر",
            "national_id": "1234512347",
            "occupation": "student",
        }

        save_extrainfo(user, extrainfo_data)

        self.assertEqual(
            {field: value for field, value in model_to_dict(user.extrainfo).items() if field in extrainfo_data},
            extrainfo_data,
        )

    def test_wrong_extra_info_field(self):
        """ Test when the input is not a extra info field.

        Expected behavior:
            - The user has no extra info model.
        """
        user, _ = User.objects.get_or_create(username="vader19")
        extrainfo_data = {
            "arabic_name2": "loool",
            "otp-crazy": True,
        }

        save_extrainfo(user, extrainfo_data)

        self.assertFalse(hasattr(user, "extrainfo"))

    def test_invalid_extra_info_field(self):
        """ Test when the input is a valid field but the value is wrong.

        Expected behavior:
            - A ValidationError is thrown.
        """
        user, _ = User.objects.get_or_create(username="vader19")
        extrainfo_data = {
            "arabic_name": "english_name",
        }

        with self.assertRaises(errors.AccountValidationError):
            save_extrainfo(user, extrainfo_data)


@ddt
class NormalizeNationalIdTestCase(TestCase):
    """Test class for normalize_national_id method."""

    @data(
        ("١٠٠٥٢٧٦٩٧٥", "1005276975"),
        ("  1005276975  ", "1005276975"),
        ("\t٢٠٠٥٢٧٦٩٧٥\n", "2005276975"),
        ("1005276975", "1005276975"),
        ("000000", "000000"),
        ("", ""),
    )
    def test_normalized_values(self, test_data):
        """Test that Arabic-Indic digits are translated and the surrounding whitespace removed.

        Expected behavior:
            - The returned value matches the expected ASCII representation.
        """
        national_id, expected = test_data

        self.assertEqual(normalize_national_id(national_id), expected)

    @data(None, 1005276975, [], {})
    def test_not_a_string(self, national_id):
        """Test that a value which is not a string is normalized to an empty string.

        Expected behavior:
            - An empty string is returned.
        """
        self.assertEqual(normalize_national_id(national_id), "")
