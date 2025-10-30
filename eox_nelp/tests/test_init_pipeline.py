"""This file contains all the test for the init_pipeline.py file.

Classes:
    RunInitPipelineTestCase: Tests cases for run_init_pipeline method.
    SetMakoTemplatesTestCase: Tests cases for set_mako_templates method.
"""
import os
from unittest.mock import call

from django.test import TestCase
from mock import patch

from eox_nelp import static as templates
from eox_nelp.edxapp_wrapper.edxmako import edxmako
from eox_nelp.init_pipeline import run_init_pipeline, set_mako_templates


class RunInitPipelineTestCase(TestCase):
    """Test class for run_init_pipeline method."""

    @patch("eox_nelp.init_pipeline.patch_form_fields_getattr")
    @patch("eox_nelp.init_pipeline.patch_generate_password")
    @patch("eox_nelp.init_pipeline.register_xapi_transformers")
    @patch("eox_nelp.init_pipeline.patch_user_gender_choices")
    @patch("eox_nelp.init_pipeline.set_mako_templates")
    def test_pipeline_execute_expected_methods(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        set_mako_templates_mock,
        patch_user_gender_choices_mock,
        register_xapi_transformers_mock,
        patch_generate_password_mock,
        patch_form_fields_getattr_mock,
    ):
        """ Test that method calls the expected methods during the pipeline execution.

        Expected behavior:
            - set_mako_templates_mock is called once.
            - patch_user_gender_choices_mock is called once.
        """
        run_init_pipeline()

        set_mako_templates_mock.assert_called_once()
        patch_user_gender_choices_mock.assert_called_once()
        register_xapi_transformers_mock.assert_called_once()
        patch_generate_password_mock.assert_called_once()
        patch_form_fields_getattr_mock.assert_called_once()


class SetMakoTemplatesTestCase(TestCase):
    """Test class for set_mako_templates method."""

    def test_edxmako_adds_expected_paths(self):
        """ Test that method adds the expected template paths.

        Expected behavior:
            - `edxmako.paths.add_lookup` is called with the expected paths.
        """
        set_mako_templates()

        edxmako.paths.add_lookup.assert_has_calls([
            call('main', os.path.dirname(templates.__file__)),
        ])
