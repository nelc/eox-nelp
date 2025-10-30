"""This file contains all the tests for the dynamic patch utilities.

Classes:
    FormFieldGetAttrPatchTestCase: Tests for dynamic attribute resolution and field handler generation.
"""
from django.test import TestCase
from mock import Mock, patch

from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.user_authn.api import patches


class FormFieldGetAttrPatchTestCase(TestCase):
    """Tests for form_field_getattr_patch function."""

    def setUp(self):
        """
        Set up mocks for configuration and request context.
        """
        self.mock_request = Mock()
        self.mock_request.LANGUAGE_CODE = "es"

    def tearDown(self):
        """Reset mocks."""
        configuration_helpers.reset_mock()
        self.mock_request.reset_mock()

    @patch("eox_nelp.user_authn.api.patches.get_current_request")
    @patch("eox_nelp.user_authn.api.patches.form_fields._add_field_with_configurable_select_options")
    def test_dynamic_handler_generation(self, mock_add_field, mock_get_request):
        """Test that form_field_getattr_patch generates a handler for configured fields.

        Expected behaviour:
            - When attribute name matches `add_<field>_field`, and field is configured,
              a callable is returned.
        """
        field_name = "hobby"
        attribute = f"add_{field_name}_field"
        mock_get_request.return_value = self.mock_request
        configuration_helpers.get_value.side_effect = lambda key, default=None: (
            ["hobby", "sport", "movie"]
            if key == "extended_profile_fields"
            else {}
        )

        handler = patches.form_field_getattr_patch(attribute)
        handler()  # invoke handler

        self.assertTrue(callable(handler))
        mock_add_field.assert_called_once_with(field_name, field_name.capitalize(), True)

    @patch("eox_nelp.user_authn.api.patches.get_current_request")
    @patch("eox_nelp.user_authn.api.patches.form_fields._add_field_with_configurable_select_options")
    def test_dynamic_handler_with_translations(self, mock_add_field, mock_get_request):
        """Test that form_field_getattr_patch applies translated labels when available.

        Expected behaviour:
            - Translation for the field is fetched from `extended_profile_fields_translations`.
            - The label passed to `_add_field_with_configurable_select_options` should use
              the localized version instead of the field name.
        """
        field_name = "sport"
        translated_label = "Deporte"
        attribute = f"add_{field_name}_field"
        mock_get_request.return_value = self.mock_request

        configuration_helpers.get_value.side_effect = lambda key, default=None: {
            "extended_profile_fields": ["sport"],
            "extended_profile_fields_translations": {
                "es": {field_name: translated_label},
            },
        }.get(key, default)

        handler = patches.form_field_getattr_patch(attribute)
        handler(is_field_required=False)

        self.assertTrue(callable(handler))
        mock_add_field.assert_called_once_with(field_name, translated_label, False)

    def test_attribute_error_for_unconfigured_field(self):
        """Test that AttributeError is raised for unconfigured fields.

        Expected behaviour:
            - When the field is not included in the site configuration, calling
              form_field_getattr_patch raises AttributeError.
        """
        configuration_helpers.get_value.side_effect = lambda key, default=None: []
        attribute = "add_unknown_field"

        with self.assertRaises(AttributeError):
            patches.form_field_getattr_patch(attribute)
