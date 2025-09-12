from eox_nelp.edxapp_wrapper.modulestore import modulestore
from opaque_keys.edx.keys import CourseKey


def get_program_metadata(course_key_string):
    """
    Retrieve program metadata for a course.


    Args:
        course_key_string: Course identifier

    Returns:
        dict: Program metadata or {} if not found
    """
    course_key = CourseKey.from_string(course_key_string)
    course_block = modulestore().get_course(course_key)
    return course_block.other_course_settings.get("program_metadata_v1", {})


def update_program_metadata(course_key_string, program_data, user):
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
    course_key = CourseKey.from_string(course_key_string)
    course_block = store.get_course(course_key)
    other_course_settings = course_block.other_course_settings
    other_course_settings["program_metadata_v1"] = program_data
    store.update_item(course_block, user.id)
