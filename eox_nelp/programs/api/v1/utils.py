from eox_nelp.edxapp_wrapper.modulestore import modulestore
from cms.djangoapps.models.settings.course_metadata import CourseMetadata
from opaque_keys.edx.keys import CourseKey
from cms.djangoapps.contentstore.views.course import update_course_advanced_settings


def get_program_metadata(course_id):
    """
    Retrieve program metadata for a course.


    Args:
        course_id: Course identifier

    Returns:
        dict: Program metadata or None if not found
    """
    course_key = CourseKey.from_string(course_id)
    course_block = modulestore().get_course(course_key, depth=0)
    course_metadata = CourseMetadata.fetch(course_block)
    program_metadata = course_metadata.get("other_course_settings", {}).get("value", {}).get("program_metadata_v1", {})
    return program_metadata


def update_program_metadata(course_id, program_data, user):
    """
    Update program metadata for a course.

    Args:
        course_id: Course identifier
        program_data: Dictionary containing program metadata to update
        user: User object for the update operation

    Returns:
        bool: True if update was successful, False otherwise
    """
    course_key = CourseKey.from_string(course_id)
    course_block = modulestore().get_course(course_key, depth=0)
    course_metadata = CourseMetadata.fetch(course_block)
    other_course_settings = course_metadata.get("other_course_settings", {})
    other_course_settings_value = other_course_settings.get("value", {})
    other_course_settings_value["program_metadata_v1"] = program_data
    other_course_settings["value"] = other_course_settings_value
    updated_data = update_course_advanced_settings(
        course_block,
        {"other_course_settings": other_course_settings},
        user,
    )
    return updated_data["other_course_settings"]["value"]["program_metadata_v1"]
