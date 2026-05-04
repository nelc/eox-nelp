"""This file contains all the NELP filters that can be implemented by the event-routing-backends library

Filters:
    XApiActorFilter: Modifies the standard ACtor in order to include the name attribute.
    XApiCourseObjectFilter: Updates course object definition.
    XApiVerbFilter: Updates verb display language key.
    XApiXblockObjectFilter: Updates object definition of xblock's events.
    XApiContextFilter: Updates the context value for any event transformer.
    XApiCertificateContextFilter: Updates the context value for a certificate created event.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx_filters import PipelineStep
from tincan import Agent, Extensions, Group, LanguageMap

from eox_nelp.edxapp_wrapper.event_routing_backends import constants
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.processors.xapi.constants import DEFAULT_LANGUAGE, XAPI_ACTIVITY_UNIT_TEST
from eox_nelp.utils import extract_course_id_from_string, get_course_from_id, get_item_label

User = get_user_model()


class XApiActorFilter(PipelineStep):
    """
    This filter modifies the xAPI actor to use 'account' as the Inverse Functional Identifier (IFI).

    It prioritizes the National ID from the user's extra information. If the National ID
    is not available, it falls back to the username. The 'name' field remains the username
    for display purposes.

    The 'account' object requires:
        - homePage: The base URL of the system.
        - name: The unique identifier (National ID or Username).
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ, unused-argument
        """
        Updates the actor agent to use an account identifier based on National ID or Username.

        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Agent>: Default Actor agent from event-routing-backends.

        Returns:
            dict: Dictionary containing the updated Agent with account credentials.
        """
        mbox = result.mbox
        email = mbox.replace("mailto:", "") if "mailto:" in mbox else mbox

        try:
            # Retrieve the user by email to access profile/extra information
            user = User.objects.get(email=email)
            extrainfo = getattr(user, 'extrainfo', None)
            national_id = getattr(extrainfo, 'national_id', None) if extrainfo else None
            identifier = str(national_id) if national_id else user.username

            result = Agent(
                name=user.username,
                account={
                    "homePage": settings.LMS_ROOT_URL,  # System's home page
                    "name": identifier
                },
                objectType="Agent"
            )
        except User.DoesNotExist:
            # If user is not found, we keep the default result provided by the pipeline
            pass

        return {
            "result": result
        }


class XApiCourseObjectFilter(PipelineStep):
    """This filter is designed to modify object attributes of an event which has a course as object, this will add
    the description field and will change the name based on the course language.

    How to set:
        OPEN_EDX_FILTERS_CONFIG = {
            "event_routing_backends.processors.xapi.enrollment_events.base_enrollment.get_object": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiCourseObjectFilter"],
                "fail_silently": False,
            },
            "event_routing_backends.processors.xapi.completion_events.base_completion.get_object": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiCourseObjectFilter"],
                "fail_silently": False,
            },
            ...
        }
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ, unused-argument
        """Modifies name and description attributes of the activity's definition.

        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Activity>: Course object activity for any kind of event

        Returns:
            Activity: Modified activity.
        """
        course_id = extract_course_id_from_string(result.id)

        if course_id and result.definition.type == constants.XAPI_ACTIVITY_COURSE:
            # Get course course data
            course = get_course_from_id(course_id)
            display_name = course["display_name"]
            description = course["short_description"]
            course_language = course.get("language")

            # Set default value if language is not found
            if not course_language or course_language == constants.EN:
                course_language = DEFAULT_LANGUAGE

            # Create new attributes based on the course properties
            definition_name = LanguageMap(**({course_language: display_name} if display_name is not None else {}))
            description = LanguageMap(**({course_language: description} if description is not None else {}))

            # Updates current result
            result.definition.name = definition_name
            result.definition.description = description

        return {
            "result": result
        }


class XApiXblockObjectFilter(PipelineStep):
    """This filter is designed to modify object attributes of events whose object is a xblock
    this will add the description field and will change the name based on the course language.

    How to set:
        OPEN_EDX_FILTERS_CONFIG = {
            "event_routing_backends.processors.xapi.problem_interaction_events.base_problems.get_object": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiXblockObjectFilter"],
                "fail_silently": False,
            },
            "event_routing_backends.processors.xapi.progress_events.base_progress.get_object": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiXblockObjectFilter"],
                "fail_silently": False,
            },
            ...
        }
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ
        """Modifies name and description attributes of the activity's definition.

        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Activity>: Module or Problem object activity for any kind of event.

        Returns:
            Activity: Modified activity.
        """
        allowed_types = [
            XAPI_ACTIVITY_UNIT_TEST,
            constants.XAPI_ACTIVITY_MODULE,
            constants.XAPI_ACTIVITY_LESSON,
            constants.XAPI_ACTIVITY_QUESTION,
        ]

        if result.definition.type in allowed_types:
            # Get component data from module descriptor block.
            usage_id = transformer.get_data("data.problem_id") or transformer.get_data("data.block_id")
            usage_key = UsageKey.from_string(usage_id)
            item = modulestore().get_item(usage_key)
            display_name = item.display_name
            label = get_item_label(item)

            # Get course language block.
            course = get_course_from_id(transformer.get_data('course_id'))
            course_language = course.get("language")

            # Set default value if language is not found
            if not course_language or course_language == constants.EN:
                course_language = DEFAULT_LANGUAGE

            if display_name:
                result.definition.name = LanguageMap({course_language: display_name})

            result.definition.description = LanguageMap(**({course_language: label} if label else {}))

        return {
            "result": result
        }


class XApiVerbFilter(PipelineStep):
    """This filter is designed to update the openedx verb default language from en to en-US.

    How to set:
        OPEN_EDX_FILTERS_CONFIG = {
            "event_routing_backends.processors.xapi.transformer.xapi_transformer.get_verb": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiVerbFilter"],
                "fail_silently": False,
            },
        }
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ, unused-argument
        """Modifies verb display key to use the eox_nelp default language.

        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Verb>: Verb related to an event.

        Returns:
            Verb: Modified verb.
        """
        if constants.EN in result.display:
            result.display = LanguageMap({DEFAULT_LANGUAGE: result.display[constants.EN]})

        return {
            "result": result
        }


class XApiContextFilter(PipelineStep):
    """This filter is designed to update the context value for any event transformer.

    How to set:
        OPEN_EDX_FILTERS_CONFIG = {
            "event_routing_backends.processors.xapi.transformer.xapi_transformer.get_context": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiContextFilter"],
                "fail_silently": False,
            },
        }
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ
        """This allows to modify the statement context for any event, the allowed modifications are
        limited by the tincan library and it's not possible to changed or updated all of them, the
        supported fields are the following:

        * registration: This must be a string that represent an UUID version 1
        * instructor: This must be a dict representation of an Agent or a list of multiple dicts.
        * team: This must be a list of dicts, each dict must be a agent representation.
        * revision: This must be a string.
        * platform: This must be a string.
        * language: This must be a valid string language.
        * extensions: This must be a dictionary.

        ** statement: Not supported.
        ** context_activities: NOT supported.

        E.G.

        {
            "XAPI_EXTRA_CONTEXT":         {
                "registration": "550e8400-e29b-41d4-a716-446655440000",
                "instructor": {
                    "name": "Jhon",
                    "mbox": "test@example.com"
                },
                "team": [
                    {
                        "name": "Peter",
                        "mbox": "peter@example.com"
                    },
                    {
                        "name": "Alex",
                        "mbox": "alex@example.com"
                    },
                    ...
                ],
                "platform": "My-great-platform",
                "language": "ar-SA",
                "extensions": {
                    "https://example.com/extensions/platform": {
                        "name": {
                            "ar-SA": "التكنولوجيا الرائدة",
                            "en-US": "Leading Tech for Training",
                        },
                    },
                },
            }
        }



        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Context>: Context related to an event.

        Returns:
            Context: Modified context.
        """
        extra_context = self._get_extra_context(transformer)
        unsupported_fields = ["context_activities", "statement"]

        for key, value in extra_context.items():
            if not hasattr(result, key) or key in unsupported_fields:
                break

            updater = getattr(self, f"_update_{key}", None)

            if updater:
                updater(result, value)   # pylint: disable=not-callable
            else:
                setattr(result, key, value)

        return {
            "result": result
        }

    def _get_extra_context(self, transformer):
        """Gets and returns an extra context based on the general settings and the course configuration.

        Arguments:
            transformer <XApiTransformer>: Transformer instance.

        Returns:
            Dict: This a dict that contains fields that should be added or updated in the event context.
        """
        xapi_course_context = {}
        course_id = transformer.get_data("course_id")
        xapi_platform_context = getattr(settings, "XAPI_EXTRA_CONTEXT", {})

        if course_id:
            course_key = CourseKey.from_string(course_id)
            course = modulestore().get_course(course_key)
            xapi_course_context = course.other_course_settings.get("XAPI_EXTRA_CONTEXT", {})

        xapi_platform_context.update(xapi_course_context)

        return xapi_platform_context

    def _update_extensions(self, context, value):
        """This updates the extensions context attribute."""
        context.extensions.update(value)

    def _update_instructor(self, context, value):
        """This updates the instructor context attribute."""
        if isinstance(value, dict):
            instructor = Agent(**value)
        elif isinstance(value, list):
            instructor = self.generate_group(value)
        else:
            raise ValueError()

        context.instructor = instructor

    def _update_team(self, context, value):
        """This updates the team context attribute."""
        if isinstance(value, list):
            team = self.generate_group(value)
        else:
            raise ValueError()

        context.team = team

    @staticmethod
    def generate_group(group_data):
        """Generate a Group instance based on the given group_data argument.

        Arguments:
            group_data<list>: List of dictionaries that represents an Agent.

        Returns:
            Group
        """
        group = Group()

        for agent_data in group_data:
            agent = Agent(**agent_data)
            group.addmember(agent)

        return group


class XApiCertificateContextFilter(PipelineStep):
    """This filter is designed to update the certificate context extensions value.

    How to set:
        OPEN_EDX_FILTERS_CONFIG = {
            "event_routing_backends.processors.xapi.transformer.xapi_transformer.get_context": {
                "pipeline": ["eox_nelp.openedx_filters.xapi.filters.XApiCertificateContextFilter"],
                "fail_silently": False,
            },
        }
    """

    def run_filter(self, transformer, result):  # pylint: disable=arguments-differ
        """This adds jws-certificate-location extension

        Arguments:
            transformer <XApiTransformer>: Transformer instance.
            result <Context>: Context related to an event.

        Returns:
            Context: Modified context.
        """
        certificate_id = transformer.get_data("data.certificate_id")

        if certificate_id:
            certificate_url = transformer.get_object_iri("certificates", certificate_id)
            extension = {"http://id.tincanapi.com/extension/jws-certificate-location": certificate_url}

            if result.extensions:
                result.extensions.update(extension)
            else:
                result.extensions = Extensions(extension)

        return {
            "result": result
        }
