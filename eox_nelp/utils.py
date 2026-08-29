"""Utils that can be used for the plugin project"""
import re
from copy import copy

from custom_reg_form.forms import ExtraInfoForm
from custom_reg_form.models import ExtraInfo
from django.forms.models import model_to_dict
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.course_overviews import get_course_overviews
from eox_nelp.edxapp_wrapper.user_api import errors

NATIONAL_ID_REGEX = r"^[1-2]\d{9}$"
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
COURSE_ID_REGEX = r'(course-v1:[^/+]+(/|\+)[^/+]+(/|\+)[^/?]+)'


def map_instance_attributes_to_dict(instance, attributes_mapping):
    """Create a dictionary that represents some fields or attributes of a instance based on
    a attributes_mapping dictionary. This dict would have key, values which the key represent the
    attribute to look in the instance and the value the key name in the output dict.
    Based in the `attributes_mapping` you should use a dict with the following config:
    {
        "key_name": "field_name"
    }
    This would check in the instace instance.field_name and the value send it to output dict
    like {"key_name": instance.field_name}
    Also its is possible to check nested fields if you declarate the field of instance separated by `__`
    eg:
    {
        "key_name": "field_level1__field_level2"
    }
    This example would check in the instace like instance.field_level1.field_level2 and in the output
    dict like {"key_name": instance.field_level1.field_level2}
    Args:
        instance (instance class): Model or instance of class to retrieved fields.
        attributes_mapping (dict): Dictionary map that has the fields to search and the keys name to output,

    Returns:
        instance_dict: dict representing the instance
    """
    instance_dict = {}
    for extra_field, instance_field in attributes_mapping.items():
        extra_value = None
        instance_level = copy(instance)
        for instance_field in instance_field.split("__"):
            if hasattr(instance_level, instance_field):
                instance_level = getattr(instance_level, instance_field)
                extra_value = instance_level

        instance_dict[extra_field] = extra_value

    return instance_dict


def check_regex(string, regex):
    """Checks if the string matches the regex.

    Args:
        string: The string to check.
        regex: The regex to match against.

    Returns:
        True if the string matches the regex, False otherwise.
    """
    pattern = re.compile(regex)

    return pattern.match(string) is not None


def normalize_national_id(national_id):
    """Normalize a national_id so it can be matched by the external services that consume it.

    Arabic-Indic digits are translated to their ASCII counterpart and the surrounding
    whitespace is removed, since those values are stored verbatim and are unmatchable otherwise.

    Args:
        national_id: The value stored as national_id.

    Returns:
        national_id <str>: The normalized national_id, an empty string when it is not a string.
    """
    if not isinstance(national_id, str):
        return ""

    return national_id.strip().translate(ARABIC_INDIC_DIGITS)


def is_valid_national_id(national_id, raise_exception=False):
    """Validate if a national_id has the shape of a national_id

    Args:
        national_id: The string of national_id to check.

    Returns:
        True if the national_id is ok, False otherwise.

    Raise:
    ValueError: This will be raised when the username are excluded dont match national Id regex.
    """
    check_national_id = check_regex(national_id, NATIONAL_ID_REGEX)

    if raise_exception and not check_national_id:
        raise ValueError(
            f"The username or national_id: {national_id} doesnt match national ID regex ({NATIONAL_ID_REGEX})",
        )

    return check_national_id


def extract_course_id_from_string(string):
    """This return a sub-string that matches the course_ir regex

    Arguments:
        string: This is a string that could contains a sub-string that matches with the course_id form.

    Returns:
        course_id <string>: Returns course id or an empty string.
    """
    matches = re.search(COURSE_ID_REGEX, string)

    if matches:
        return matches.group()

    return ""


def get_course_from_id(course_id):
    """
    Get Course object using the `course_id`.

    Arguments:
        course_id (str) :   ID of the course

    Returns:
        Course
    """
    course_key = CourseKey.from_string(course_id)
    course_overviews = get_course_overviews([course_key])

    if course_overviews:
        return course_overviews[0]

    raise ValueError(f"Course with id {course_id} does not exist.")


def get_item_label(item):
    """By definition the label of a Problem is the text between double greater and lees than
    symbols, example, >>label<<, this method extracts and returns that information from the item
    markdown value.

    Arguments:
        item <XModuleDescriptor>: This is a specification for an element of a course.
            This case should be a problem.
    Returns:
        label <string>: Label data if it's found otherwise empty string.
    """
    if not (hasattr(item, "markdown") and isinstance(item.markdown, str)):
        return ""

    regex = re.compile(r'>>\s*(.*?)\s*<<')
    matches = regex.search(item.markdown)

    if matches:
        return matches.group(1)

    return ""


def camel_to_snake(string):
    """Convert string from camel case to snake case.

    Args:
        string: String in camel case format.

    Returns:
        String in snake case.
    """
    return re.sub(r'(?<!^)(?=[A-Z])', '_', string).lower()


def save_extrainfo(user, data):
    """Given a user save in extrainfo a value or values in desired fields.
    If the extrainfo doesnt exist, the extrainfo model is created

    Args:
        user (User): user instace
        data (dict): extra info data in dict format
    """
    validated_data = {field: value for field, value in data.items() if hasattr(ExtraInfo, field)}

    if not validated_data:
        return

    extra_info, _ = ExtraInfo.objects.get_or_create(user=user)  # pylint: disable=no-member
    form_data = model_to_dict(extra_info)
    form_data.update(validated_data)

    form = ExtraInfoForm(form_data, instance=extra_info)

    if form.is_valid():
        form.save()
    else:
        raise errors.AccountValidationError(form.errors)
