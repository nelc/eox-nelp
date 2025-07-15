"""This file contains all the test for notifications/utils.py file.

Classes:
    SendEmailMultiAlternativeTestCase: Test `send_email_multialternative` method.
    GetXBlockFromUsageKeyStringTestCase: Test `get_xblock_from_usage_key_string` method.
    GetXBlockCourseFromUsageKeyStringTestCase: Test `get_xblock_course_from_usage_key_string` method.
"""
from django.core import mail
from django.test import TestCase
from opaque_keys.edx.keys import UsageKey

from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.notifications.utils import (
    get_xblock_course_from_usage_key_string,
    get_xblock_from_usage_key_string,
    send_email_multialternative,
)


class SendEmailMultiAlternativeTestCase(TestCase):
    """Test class for function `send_email_multialternative`."""

    def test_send_email_multialternative(self):
        """Test correct behaviour of sending email with
        method `send_email_multialternative`.
        Expected behavior:
            - The number of emails sent is numsent
            - The email was sent with the correct subject.
            - The email was sent with the correct plaintext message.
            - The email was sent with the correct HTML message.
            - The email was sent to the correct recipient.
            - The email was sent from the correct email address (if specified)
        """
        subject = "Test email"
        plaintext_msg = "This is a test email"
        html_msg = "<html><body><p>This is a test email</p></body></html>"
        recipient_emails = ["vader@example.com", "dooku@example.com"]
        from_email = "palpatine@example.com"

        # Call the function and get the number of emails sent
        num_sent = send_email_multialternative(subject, plaintext_msg, html_msg, recipient_emails, from_email)

        self.assertEqual(len(mail.outbox), num_sent)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, subject)
        self.assertEqual(sent_email.body, plaintext_msg)
        self.assertEqual(sent_email.alternatives[0][0], html_msg)
        self.assertEqual(sent_email.to, recipient_emails)
        self.assertEqual(sent_email.from_email, from_email)


class GetXBlockFromUsageKeyStringTestCase(TestCase):
    """Test class for function `get_xblock_from_usage_key_string`."""

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()

    def test_get_xblock_from_usage_key_string(self):
        """Test get the usage_xblock using usage_key_string.
         Expected behavior:
            - modulestore().get_item is called with the right values.
        """
        usage_key_string = "block-v1:obi+wan+course+type@sequential+block@fb7951843736445bb46f30bbb60134ea"
        usage_key = UsageKey.from_string(usage_key_string)

        get_xblock_from_usage_key_string(usage_key_string)

        modulestore().get_item.assert_called_with(usage_key, depth=None)

    def test_get_xblock_from_wrong_usage_key_string(self):
        """Test get the usage_xblock using wrong usage_key_string.
        Expected behavior:
            - modulestore().get_item is not called.
        """
        usage_key_string = "block-wrong:obi+wan+course+type@sequential+block@fb7951843736445bb46f30bbb60134ea"

        get_xblock_from_usage_key_string(usage_key_string)

        modulestore().get_item.assert_not_called()


class GetXBlockCourseFromUsageKeyStringTestCase(TestCase):
    """Test class for function `get_xblock_course_from_usage_key_string`."""

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()

    def test_get_xblock_course_from_usage_key_string(self):
        """Test get the course_xblock using usage_key_string.
         Expected behavior:
            - modulestore().get_course is called with the right values.
        """
        usage_key_string = "block-v1:obi+wan+course+type@sequential+block@fb7951843736445bb46f30bbb60134ea"
        course_key = UsageKey.from_string(usage_key_string).course_key

        get_xblock_course_from_usage_key_string(usage_key_string)

        modulestore().get_course.assert_called_with(course_key, depth=None)

    def test_get_xblock_course_from_wrong_usage_key_string(self):
        """Test get the course_xblock using usage_key_string.
         Expected behavior:
            - modulestore().get_course is not called.
        """
        usage_key_string = "block-wrong:obi+wan+course+type@sequential+block@fb7951843736445bb46f30bbb60134ea"

        get_xblock_course_from_usage_key_string(usage_key_string)

        modulestore().get_course.assert_not_called()
