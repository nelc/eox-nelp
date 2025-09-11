from importlib import import_module

from eox_nelp.edxapp_wrapper.modulestore import modulestore
from opaque_keys.edx.keys import CourseKey


def _import_cms_object(module_path, attribute_name=None):
    """Import CMS-only objects lazily to avoid ImportError in LMS/test envs.

    Returns a tuple: (CourseMetadata, update_course_advanced_settings)
    """
    try:
        module = import_module(module_path)
        return module if attribute_name is None else getattr(module, attribute_name)
    except Exception as exc:  # pragma: no cover - defensive
        raise ImportError(
            f"CMS module {module_path} with attribute {attribute_name} not available."
            f"Ensure CMS context when using programs utils.-> {exc}"
        ) from exc


def get_program_metadata(course_key_string):
    """
    Retrieve program metadata for a course.


    Args:
        course_key_string: Course identifier

    Returns:
        dict: Program metadata or None if not found
    """
    course_key = CourseKey.from_string(course_key_string)
    course_block = modulestore().get_course(course_key, depth=0)
    CourseMetadata = _import_cms_object("cms.djangoapps.models.settings.course_metadata", "CourseMetadata")
    course_metadata = CourseMetadata.fetch(course_block)
    program_metadata = course_metadata.get("other_course_settings", {}).get("value", {}).get("program_metadata_v1", {})
    return program_metadata


def update_program_metadata(course_key_string, program_data, user):
    """
    Update program metadata for a course.

    Args:
        course_id: Course identifier
        program_data: Dictionary containing program metadata to update
        user: User object for the update operation

    Returns:
        bool: True if update was successful, False otherwise
    """
    course_key = CourseKey.from_string(course_key_string)
    course_block = modulestore().get_course(course_key, depth=0)
    CourseMetadata = _import_cms_object("cms.djangoapps.models.settings.course_metadata", "CourseMetadata")
    update_course_advanced_settings = _import_cms_object("cms.djangoapps.contentstore.views.course", "update_course_advanced_settings")
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
