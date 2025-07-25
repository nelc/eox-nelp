"""This file contains all the test for tasks.py file.
Classes:
    CreateExternalCertificateTestCase: Test the different method for create
    external certificates:
      - create_external_certificate_directly
      - trigger_external_certificate_sqs
      - create_external_certificate
"""
import json
import unittest

from django.conf import settings
from django.test import override_settings
from mock import patch

from eox_nelp.external_certificates.tasks import (
    SQSClient,
    create_external_certificate,
    create_external_certificate_directly,
    trigger_external_certificate_sqs,
)


class ExternalCertificatesMixin:
    """Mock to reuse for external certificates test cases"""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup for external certificates tasks"""
        self.certificate_data = {
            "this": "is_a_test",
        }
        self.user_id = "1"
        self.course_id = "course-v1:test+CS304+2025_T3"


class CreateExternalCertificateTestCase(ExternalCertificatesMixin, unittest.TestCase):
    """Test class for create_external_certificate function"""

    @patch("eox_nelp.external_certificates.tasks.create_external_certificate_directly")
    @patch("eox_nelp.external_certificates.tasks.trigger_external_certificate_sqs")
    def test_certificate_creation_directly_way(self, certificate_sqs_mock, certificate_directly_mock):
        """Test certificate creation directly on method `create_external_certificate`.

        Expected behavior:
            - certificate_directly_mock is called with desired parameters.
            - certificate_sqs_mock is not called.
        """
        create_external_certificate(
            external_certificate_data=self.certificate_data,
            user_id=self.user_id,
            course_id=self.course_id,
        )

        certificate_directly_mock.delay.assert_called_once_with(external_certificate_data=self.certificate_data)
        certificate_sqs_mock.delay.assert_not_called()

    @override_settings(USE_SQS_FLOW_FOR_EXTERNAL_CERTIFICATES=True)
    @patch("eox_nelp.external_certificates.tasks.create_external_certificate_directly")
    @patch("eox_nelp.external_certificates.tasks.trigger_external_certificate_sqs")
    def test_certificate_creation_sqs_way(self, trigger_certificate_sqs_mock, certificate_directly_mock):
        """Test sqs way on method `create_external_certificate`.

        Expected behavior:
            - certificate_directly_mock is not called.
            - certificate_sqs_mock  is called with desired parameters.
        """
        create_external_certificate(
            external_certificate_data=self.certificate_data,
            user_id=self.user_id,
            course_id=self.course_id,
        )

        certificate_directly_mock.delay.assert_not_called()
        trigger_certificate_sqs_mock.delay.assert_called_once_with(
            external_certificate_data=self.certificate_data,
            user_id=self.user_id,
            course_id=self.course_id,
        )


class CreateExternalCertificateDirectlyTestCase(ExternalCertificatesMixin, unittest.TestCase):
    """Test class for create_external_certificate_directly task"""

    @override_settings(EXTERNAL_CERTIFICATES_EXTRA_HEADERS={"Authorization": "Bearer test-token"})
    @patch("eox_nelp.external_certificates.tasks.ExternalCertificatesApiClient")
    def test_certificate_creation_directly(self, api_mock):
        """Test standard call with the required parameters of task `create_external_certificate_directly`.

        Expected behavior:
            - api_mock was called once.
            - create_external_certificate method from api client was called with the right parameters.
        """
        create_external_certificate_directly(self.certificate_data)

        api_mock.assert_called_once()
        api_mock.return_value.create_external_certificate.assert_called_once_with(self.certificate_data)


class TriggerExternalCertificateSQSTestCase(ExternalCertificatesMixin, unittest.TestCase):
    """Test class for trigger_external_certificate_sqs task"""

    @override_settings(
        SQS_CERTIFICATES_URL="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        SQS_AWS_ACCESS_KEY_ID="test_key_id",
        SQS_AWS_SECRET_ACCESS_KEY="test_secret_key",
        LMS_BASE="test.tenant.com",
    )
    @patch.object(SQSClient, "send_message")
    def test_trigger_sqs_certificate_success(self, mock_sqs_send_message):
        """
        Test success sqs flow of task `trigger_external_certificate_sqs`.
        Expected behavior:
            - The SQSClient send_message method should be called with the correct data.
            - The success log message should be generated.
        """
        sqs_response = {
            'MD5OfMessageBody': '273a19066c707ff14ab196eabee307be',
            'MD5OfMessageAttributes': '258aa076f155ad55026f2b3c69f761d0',
            'MessageId': '8915b35a-5430-4c49-9c1a-2348663eebdd',
        }

        mock_sqs_send_message.return_value = sqs_response
        message_attributes = {
            "UserId": {"StringValue": self.user_id, "DataType": "String"},
            "CourseId": {"StringValue": self.course_id, "DataType": "String"},
            "TriggerDomain": {
                "StringValue": getattr(settings, "LMS_BASE", None),
                "DataType": "String",
            },
        }

        with self.assertLogs("eox_nelp.external_certificates.tasks", level="INFO") as log:
            trigger_external_certificate_sqs(
                external_certificate_data=self.certificate_data,
                user_id=self.user_id,
                course_id=self.course_id,
            )

        mock_sqs_send_message.assert_called_once_with(
            message_body=json.dumps(self.certificate_data),
            message_attributes=message_attributes,
        )
        self.assertIn(
            (
                f"External certificate triggered with  MessageId {sqs_response['MessageId']} "
                f"created successfully for user_id {self.user_id} and course_id {self.course_id}."
            ),
            log.output[0],
        )

    @override_settings(
        SQS_CERTIFICATES_URL="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        SQS_AWS_ACCESS_KEY_ID="test_key_id",
        SQS_AWS_SECRET_ACCESS_KEY="test_secret_key",
        LMS_BASE="test.tenant.com",
    )
    @patch.object(SQSClient, "send_message")
    def test_trigger_sqs_certificate_failure(self, mock_sqs_send_message):
        """
        Test failture sqs flow of task `trigger_external_certificate_sqs`.
        Expected behavior:
            - The SQSClient send_message method should be called with the correct data.
            - The failure log message should be generated.
        """
        sqs_response = None
        mock_sqs_send_message.return_value = sqs_response
        message_attributes = {
            "UserId": {"StringValue": self.user_id, "DataType": "String"},
            "CourseId": {"StringValue": self.course_id, "DataType": "String"},
            "TriggerDomain": {
                "StringValue": getattr(settings, "LMS_BASE", None),
                "DataType": "String",
            },
        }

        with self.assertLogs("eox_nelp.external_certificates.tasks", level="ERROR") as log:
            trigger_external_certificate_sqs(
                external_certificate_data=self.certificate_data,
                user_id=self.user_id,
                course_id=self.course_id,
            )

        mock_sqs_send_message.assert_called_once_with(
            message_body=json.dumps(self.certificate_data),
            message_attributes=message_attributes,
        )
        self.assertIn(
            (
                f"Failed to trigger external certificate for user_id {self.user_id} and course_id {self.course_id}. "
                f"Response: {sqs_response}"
            ),
            log.output[0],
        )
