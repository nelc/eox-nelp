"""Programs API v1 utilities module.

This module provides utility functions for managing program metadata
in the context of course programs. It includes functions to retrieve
and update program metadata associated with courses.
"""
import logging
from datetime import datetime

from hijridate import Gregorian
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.programs.api.v1.constants import TYPES_OF_ACTIVITY_MAPPING

logger = logging.getLogger(__name__)


def get_program_metadata(course_id):
    """
    Retrieve program metadata for a course.


    Args:
        course_id: Course identifier

    Returns:
        dict: Program metadata or {} if not found
    """
    course_key = CourseKey.from_string(course_id)
    course_block = modulestore().get_course(course_key)
    return course_block.other_course_settings.get("program_metadata_v1", {})


def update_program_metadata(course_id, program_data, user):
    """
    Update program metadata for a course.

    Args:
        course_id: Course identifier
        program_data: Dictionary containing program metadata to update
        user: User object for the update operation

    Returns:
        None: The function does not return any value but performs an update in the **modulestore**.
    """
    store = modulestore()
    course_key = CourseKey.from_string(course_id)
    course_block = store.get_course(course_key)
    other_course_settings = course_block.other_course_settings
    other_course_settings["program_metadata_v1"] = program_data
    store.update_item(course_block, user.id)


def get_program_lookup_representation(course_api_data):
    """
    Generate a lookup representation for program metadata.

    Args:
        course_api_data: Dictionary containing course api data representation.

    Returns:
        dict: Lookup representation with selected fields
    """
    program_metadata = get_program_metadata(course_api_data["course_id"])
    data_start_iso = convert_to_isoformat(course_api_data.get("start"))
    data_end_iso = convert_to_isoformat(course_api_data.get("end"))
    program_lookup_representation = {
        "program_name": course_api_data.get("name"),
        "program_code": program_metadata.get("program_code"),
        "training_location": "FutureX",
        "data_start": data_start_iso,
        "data_start_hijri": Gregorian.fromisoformat(data_start_iso).to_hijri().isoformat() if data_start_iso else None,
        "date_end": data_end_iso,
        "date_end_hijri": Gregorian.fromisoformat(data_end_iso).to_hijri().isoformat() if data_end_iso else None,
        "trainer_type": 10,
        "type_of_activity": TYPES_OF_ACTIVITY_MAPPING.get(program_metadata.get("type_of_activity", -1)),
        "type_of_activity_id": program_metadata.get("type_of_activity"),
        "unit": "hour",
        "duration": hms_to_int(course_api_data.get("effort")) or 0,
        "mandatory": program_metadata.get("mandatory"),
        "program_approve": program_metadata.get("program_approve"),
        "code": course_api_data["course_id"],
    }
    return program_lookup_representation


def convert_to_isoformat(date_string):
    """
    Parses a datetime string ending with 'Z' (for UTC) and returns
    a timezone-aware datetime object in ISO 8601 format.

    Args:
        date_string (str): A string in the format 'YYYY-MM-DDTHH:MM:SSZ'.

    Returns:
        str: The timezone-aware datetime string in ISO 8601 format.
    """
    if not date_string:
        return None
    # Replace 'Z' with '+00:00' to match the expected format for UTC offset
    try:
        dt_object = datetime.strptime(date_string.replace('Z', '+00:00'), '%Y-%m-%dT%H:%M:%S%z')
        return dt_object.date().isoformat()
    except ValueError as e:
        logger.error("Error parsing date string: %s", e)
        return None


def hms_to_int(time_str):
    """
    Converts a time string to an integer representing total hours,
    rounding to the nearest whole number. Handles both "HH:MM" and "HH" formats.

    Args:
        time_str: The time string (e.g., "2:30" or "2").

    Returns:
        An integer representing the total hours, rounded to the nearest whole number.
        or None if input is invalid and there is some error.
    """
    if not time_str:
        return None
    try:
        if ":" in time_str:
            hours, minutes = map(int, time_str.split(":"))

            if minutes < 0 or minutes >= 60:
                minutes = 0  # Reset invalid minutes to 0

            return round(hours + (minutes / 60))
        return int(time_str)
    except ValueError as e:
        logger.warning("Error converting time string: %s", e)
        return None
