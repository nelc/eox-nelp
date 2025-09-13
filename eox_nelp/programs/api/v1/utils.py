"""Programs API v1 utilities module.

This module provides utility functions for managing program metadata
in the context of course programs. It includes functions to retrieve
and update program metadata associated with courses.
"""
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.modulestore import modulestore


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
    program_metadata = get_program_metadata(course_api_data["id"])

    program_lookup_representation = {
        "Program_name": course_api_data.get("name"),
        "Program_code": program_metadata.get("Program_code"),
        "Training_location": "FutureX",
        "Date_Start": course_api_data.get("start"),
        "Date_End": course_api_data.get("end"),
        "Trainer_type": 10,
        "Type_of_Activity": TYPES_OF_ACTIVITY_MAPPING.get(program_metadata.get("Type_of_Activity", -1)),
        "Type_of_Activity_id": program_metadata.get("Type_of_Activity"),
        "Unit": "hour",
        "duration": int(course_api_data.get("effort") or 0),
        "Mandatory": program_metadata.get("Mandatory"),
        "Program_ABROVE": program_metadata.get("Program_ABROVE"),
        "Code": course_api_data["id"],
    }
    return program_lookup_representation



TYPES_OF_ACTIVITY_MAPPING = {
    135: "التدريب - التدريب المباشر",
    155: "التدريب - التدريب الإلكتروني",
    165: "برنامج الاستثمار الأمثل (برامج قصيرة)",
    175: "برنامج الاستثمار الأمثل (برامج طويلة)",
    190: "الملتقيات - المؤتمرات",
    195: "الملتقيات - اللقاءات التربوية",
    200: "الملتقيات - المحاضرات",
    205: "الملتقيات - الندوات",
    270: "التعلم التشاركي - الزيارات الميدانية",
    55: "ورش العمل - ورش العمل",
    65: "التعلم التشاركي - الدروس التطبيقية",
    75: "التعلم التشاركي - دورة بحث الدرس"
}
