"""This file contains all the test for the init_pipeline.py file.

Classes:
    RunInitPipelineTestCase: Tests cases for run_lms_init_pipeline method.
    SetMakoTemplatesTestCase: Tests cases for set_mako_templates method.
"""
import os
from unittest.mock import call

from celery import current_app
from django.test import TestCase
from mock import DEFAULT, patch

from eox_nelp import static as templates
from eox_nelp.edxapp_wrapper.edxmako import edxmako
from eox_nelp.init_pipeline import register_learner_email_tasks, run_lms_init_pipeline, set_mako_templates


class RunInitPipelineTestCase(TestCase):
    """Test class for run_lms_init_pipeline method."""

    @patch("eox_nelp.init_pipeline.patch_form_fields_getattr")
    @patch("eox_nelp.init_pipeline.patch_generate_password")
    @patch("eox_nelp.init_pipeline.register_xapi_transformers")
    @patch("eox_nelp.init_pipeline.patch_user_gender_choices")
    @patch("eox_nelp.init_pipeline.set_mako_templates")
    def test_pipeline_execute_expected_methods(
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
        with patch("eox_nelp.init_pipeline.patch_scorm_get_file_path") as patch_scorm_get_file_path_mock:
            run_lms_init_pipeline()

        set_mako_templates_mock.assert_called_once()
        patch_user_gender_choices_mock.assert_called_once()
        register_xapi_transformers_mock.assert_called_once()
        patch_generate_password_mock.assert_called_once()
        patch_form_fields_getattr_mock.assert_called_once()
        patch_scorm_get_file_path_mock.assert_called_once()

    @patch.multiple(
        "eox_nelp.init_pipeline",
        patch_user_gender_choices=DEFAULT,
        set_mako_templates=DEFAULT,
        register_xapi_transformers=DEFAULT,
        update_permissions=DEFAULT,
        patch_generate_password=DEFAULT,
        patch_registration_form_factory=DEFAULT,
        patch_form_fields_getattr=DEFAULT,
        disconnect_update_last_login_signal=DEFAULT,
        take_over_core_enrollment_route=DEFAULT,
        register_learner_email_tasks=DEFAULT,
        patch_scorm_get_file_path=DEFAULT,
    )
    def test_pipeline_registers_learner_email_tasks(self, **mocks):
        """The LMS pipeline loads the learner-email tasks (Studio's pipeline does not).

        Expected behavior:
            - register_learner_email_tasks is called once.
        """
        run_lms_init_pipeline()

        mocks["register_learner_email_tasks"].assert_called_once()


class RegisterLearnerEmailTasksTestCase(TestCase):
    """Test class for register_learner_email_tasks method."""

    def test_tasks_are_registered_in_celery(self):
        """A worker that ran the LMS pipeline knows every learner-email task by name.

        Expected behavior:
            - The three task names are in the Celery app's task registry.
        """
        register_learner_email_tasks()

        for name in (
            "eox_nelp.learner_emails.tasks.send_certificate_ready_email",
            "eox_nelp.learner_emails.tasks.send_learning_starts_email",
            "eox_nelp.learner_emails.tasks.send_completion_reminder_email",
        ):
            self.assertIn(name, current_app.tasks)


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
