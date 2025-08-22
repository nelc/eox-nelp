"""
App configuration for eox_nelp.
"""

from __future__ import unicode_literals

from django.apps import AppConfig

from eox_nelp.init_pipeline import run_init_pipeline


class EoxNelpConfig(AppConfig):
    """
    Nelp plugin for custom development. configuration.
    """
    name = 'eox_nelp'
    verbose_name = 'Nelp plugin for custom development.'
    plugin_app = {
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'eox-nelp',
                'regex': r'^eox-nelp/',
                'relative_path': 'urls',
            },
        },
        'settings_config': {
            'lms.djangoapp': {
                'test': {'relative_path': 'settings.test'},
                'common': {'relative_path': 'settings.common'},
                'production': {'relative_path': 'settings.production'},
                'devstack': {'relative_path': 'settings.devstack'},
            },
        },
        'signals_config': {
            'lms.djangoapp': {
                'relative_path': 'signals.receivers',
                'receivers': [
                    {
                        'receiver_func_name': 'block_completion_progress_publisher',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'block_completion_publisher_receviver',
                        'sender_path': 'completion.models.BlockCompletion',
                    },
                    {
                        'receiver_func_name': 'emit_initialized_course_event',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'emit_initialized_course_event_receviver',
                        'sender_path': 'completion.models.BlockCompletion',
                    },
                    {
                        'receiver_func_name': 'course_grade_changed_progress_publisher',
                        'signal_path': 'openedx.core.djangoapps.signals.signals.COURSE_GRADE_CHANGED',
                        'dispatch_uid': 'course_grade_publisher_receiver',
                    },
                    {
                        'receiver_func_name': 'certificate_publisher',
                        'signal_path': 'openedx_events.learning.signals.CERTIFICATE_CREATED',
                        'dispatch_uid': 'certificate_publisher_receiver',
                    },
                    {
                        'receiver_func_name': 'enrollment_publisher',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'enrollment_publisher_receiver',
                        'sender_path': 'common.djangoapps.student.models.CourseEnrollment',
                    },
                    {
                        'receiver_func_name': 'create_usersignupsource_by_enrollment',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'create_usersignupsource_by_enrollment_receiver',
                        'sender_path': 'common.djangoapps.student.models.CourseEnrollment',
                    },
                    {
                        'receiver_func_name': 'update_payment_notifications',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'update_payment_notifications_receiver',
                        'sender_path': 'common.djangoapps.student.models.CourseEnrollment',
                    },
                    {
                        'receiver_func_name': 'include_tracker_context',
                        'signal_path': 'celery.signals.before_task_publish',
                    },
                    {
                        'receiver_func_name': 'update_async_tracker_context',
                        'signal_path': 'celery.signals.task_prerun',
                    },
                    {
                        'receiver_func_name': 'emit_subsection_attempt_event',
                        'signal_path': 'lms.djangoapps.grades.signals.signals.PROBLEM_WEIGHTED_SCORE_CHANGED',
                    },
                    {
                        'receiver_func_name': 'emit_subsection_attempt_event',
                        'signal_path': 'lms.djangoapps.grades.signals.signals.SUBSECTION_OVERRIDE_CHANGED',
                    },
                    {
                        'receiver_func_name': 'mt_course_completion_handler',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'mt_course_completion_receviver',
                        'sender_path': 'completion.models.BlockCompletion',
                    },
                    {
                        'receiver_func_name': 'mt_course_passed_handler',
                        'signal_path': 'openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED',
                        'dispatch_uid': 'mt_course_passed_receiver',
                    },
                    {
                        'receiver_func_name': 'mt_course_failed_handler',
                        'signal_path': 'openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_FAILED',
                        'dispatch_uid': 'mt_course_failed_receiver',
                    },
                    {
                        'receiver_func_name': 'pearson_vue_course_completion_handler',
                        'signal_path': 'django.db.models.signals.post_save',
                        'dispatch_uid': 'pearson_vue_course_completion_receiver',
                        'sender_path': 'completion.models.BlockCompletion',
                    },
                    {
                        'receiver_func_name': 'pearson_vue_course_passed_handler',
                        'signal_path': 'openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED',
                        'dispatch_uid': 'pearson_vue_course_passed_receiver',
                    },
                ],
            },
        },
    }

    def ready(self):
        """
        Method to perform actions after apps registry is ended.
        """
        run_init_pipeline()


class EoxNelpCMSConfig(AppConfig):
    """App configuration"""
    name = 'eox_nelp'
    verbose_name = "Nelp Openedx Extensions"

    plugin_app = {
        'url_config': {
            'cms.djangoapp': {
                'namespace': 'eox-nelp',
                'regex': r'^eox-nelp/',
                'relative_path': 'cms_urls',
            },
        },
        'settings_config': {
            'cms.djangoapp': {
                'test': {'relative_path': 'settings.test'},
                'common': {'relative_path': 'settings.common'},
                'production': {'relative_path': 'settings.production'},
                'devstack': {'relative_path': 'settings.devstack'},
            },
        },
        'signals_config': {
            'cms.djangoapp': {
                'relative_path': 'signals.receivers',
                'receivers': [
                    {
                        'receiver_func_name': 'create_course_notifications',
                        'signal_path': 'xmodule.modulestore.django.COURSE_PUBLISHED',
                        'dispatch_uid': 'create_course_notifications_receiver',
                    },
                    {
                        'receiver_func_name': 'receive_course_created',
                        'signal_path': 'openedx_events.content_authoring.signals.COURSE_CREATED',
                        'dispatch_uid': 'course_published_receiver',
                    }
                ],
            },
        },
    }
