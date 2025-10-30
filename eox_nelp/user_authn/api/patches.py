"""
This module defines utility functions for dynamic runtime patching.

Functions:

    form_field_getattr_patch:
        Defines a dynamic attribute resolver that returns a callable when
        the accessed attribute matches a specific naming pattern.
"""
import re

from crum import get_current_request

from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.edxapp_wrapper.user_authn import form_fields


def form_field_getattr_patch(attribute):
    """
    Resolves dynamic attribute access based on a naming pattern.

    If the given attribute name matches the expected pattern (e.g. `add_<field_name>_field`)
    and the corresponding field is listed in the site configuration, a callable is returned
    that can generate the field definition at runtime.

    Args:
        attribute (str): Attribute name being accessed.

    Returns:
        function: Callable that generates a form field definition.

    Raises:
        AttributeError: If the attribute name does not correspond to a configured field.
    """

    def _generate_handler(field_name):
        """
        Creates a callable for generating a form field definition.

        This helper retrieves field metadata such as label translations from
        site configuration and prepares a function that can be invoked to
        construct the appropriate form field.

        Args:
            field_name (str): Name of the field to generate.

        Returns:
            function: Callable that, when executed, creates the field definition.
        """
        request = get_current_request()

        extended_profile_fields_translations = configuration_helpers.get_value(
            "extended_profile_fields_translations",
            {},
        )
        translations = extended_profile_fields_translations.get(request.LANGUAGE_CODE, {})
        label = translations.get(field_name, field_name).capitalize()

        def handler(is_field_required=True):
            """
            Creates a form field using the given parameters.

            Args:
                is_field_required (bool): Whether the field is mandatory. Defaults to True.

            Returns:
                Any: Field instance created by the underlying form field utility.
            """
            # pylint: disable=protected-access
            return form_fields._add_field_with_configurable_select_options(field_name, label, is_field_required)

        return handler

    pattern = r"^add_(?P<field_name>.+?)_field$"

    field_name = re.match(pattern, attribute).group('field_name')
    extended_profile_fields = configuration_helpers.get_value("extended_profile_fields", [])

    if field_name in extended_profile_fields:
        return _generate_handler(field_name)

    raise AttributeError()
