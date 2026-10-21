"""
Unit tests for Certificates API v1 views.
"""
from datetime import datetime, timezone

from custom_reg_form.models import ExtraInfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from edx_toggles.toggles.testutils import override_waffle_switch
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from mock import patch
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.access import ENFORCE_TENANT_SCOPED_LOOKUPS
from eox_nelp.edxapp_wrapper.certificates import api as certificates_api
from eox_nelp.edxapp_wrapper.certificates import utils as certificates_utils
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview, get_course_overviews
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.tests.utils import set_key_values

User = get_user_model()
GeneratedCertificate = get_generated_certificate()

NATIONAL_ID = "1234567890"
CERTIFICATE_ID = "2c97649425bb49189470f05bf7d98c1a"
COURSE_ID = "course-v1:test+Cx105+2022_T4"
ISSUE_DATE = datetime(2024, 5, 29, 17, 24, tzinfo=timezone.utc)
ENGLISH_NAME = "Test Student"
ARABIC_NAME = "مسؤل"


class UserCertificateListViewTests(APITestCase):
    """
    Test suite for the UserCertificateListView API view.
    """

    def setUp(self):
        """
        Set up the test data and mock clients for the test suite.
        """
        self.url = reverse("certificates-api:v1:user-certificate-list", args=[NATIONAL_ID])
        self.detail_url = reverse("certificates-api:v1:user-certificate-detail", args=[CERTIFICATE_ID])
        self.student, _ = User.objects.get_or_create(
            username="student",
            email="student@example.com",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=self.student,
            arabic_name=ARABIC_NAME,
            national_id=NATIONAL_ID,
            occupation="student",
        )
        CourseOverview.objects.get_or_create(
            id=CourseKey.from_string(COURSE_ID),
            org="test",
        )
        GeneratedCertificate.objects.create(**{
            'user': self.student,
            'course_id': CourseKey.from_string(COURSE_ID),
            'grade': '71.0',
            'status': 'downloadable',
            'mode': 'honor',
            "verify_uuid": CERTIFICATE_ID,

        })
        self.staff_user = User.objects.create_user(
            username="staff_user",
            email="staff@example.com",
            password="testpassword",
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="regular@example.com",
            password="testpassword",
            is_staff=False
        )
        certificates_api.display_date_for_certificate.return_value = ISSUE_DATE
        certificates_utils.get_certificate_url.return_value = f"/certificates/{CERTIFICATE_ID}"
        get_course_overviews.return_value = [{"display_name": "TestingCourse"}]
        # Tenant scope: by default the request tenant owns org "test" and the student is a member of it.
        tenant_orgs_patcher = patch("eox_nelp.certificates.api.v1.views.get_tenant_orgs", return_value={"test"})
        member_patcher = patch("eox_nelp.certificates.api.v1.views.is_tenant_member", return_value=True)
        self.tenant_orgs_mock = tenant_orgs_patcher.start()
        self.member_mock = member_patcher.start()
        self.addCleanup(tenant_orgs_patcher.stop)
        self.addCleanup(member_patcher.stop)

    @staticmethod
    def expected_certificate_data():
        """
        Build the expected serialized representation of the certificate created on setUp.

        Returns:
            dict: expected certificate payload.
        """
        return {
            "certificate_id": CERTIFICATE_ID,
            "tenant": "test.openedx.io",
            "org": "test",
            "course_id": COURSE_ID,
            "course_name": "TestingCourse",
            "status": "downloadable",
            "mode": "honor",
            "issue_date": ISSUE_DATE.isoformat(),
            "certificate_url": f"http://test.openedx.io/certificates/{CERTIFICATE_ID}",
        }

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificates_success(self):
        """
        Test successful retrieval of user certificates by national ID.

        Expected behavior:
            - Status code 200.
            - Return expected username.
            - Return expected national ID.
            - Return expected english and arabic names.
            - Return expected serialized certificates.
        """
        self.client.force_authenticate(user=self.staff_user)
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student")
        self.assertEqual(response.data["national_id"], NATIONAL_ID)
        self.assertEqual(response.data["english_name"], ENGLISH_NAME)
        self.assertEqual(response.data["arabic_name"], ARABIC_NAME)
        self.assertEqual(response.data["certificates"], [self.expected_certificate_data()])

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificate_by_certificate_id_success(self):
        """
        Test successful retrieval of a single certificate by its certificate ID.

        Expected behavior:
            - Status code 200.
            - Return the owner details of the matched certificate.
            - Return only the certificate matching the requested certificate ID.
        """
        self.client.force_authenticate(user=self.staff_user)
        GeneratedCertificate.objects.create(**{
            'user': self.student,
            'course_id': CourseKey.from_string("course-v1:test+Cx106+2022_T4"),
            'grade': '80.0',
            'status': 'downloadable',
            'mode': 'honor',
            "verify_uuid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        })
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student")
        self.assertEqual(response.data["national_id"], NATIONAL_ID)
        self.assertEqual(response.data["english_name"], ENGLISH_NAME)
        self.assertEqual(response.data["arabic_name"], ARABIC_NAME)
        self.assertEqual(response.data["certificates"], [self.expected_certificate_data()])

    def test_get_certificate_by_certificate_id_not_found(self):
        """
        Test retrieval attempt with a certificate ID that matches no certificate.

        Expected behavior:
            - Status code 404.
            - Return error message indicating the certificate was not found.
        """
        url = reverse("certificates-api:v1:user-certificate-detail", args=["f" * 32])
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["error"],
            "Certificate with the provided certificate ID was not found."
        )

    def test_get_certificates_user_not_found(self):
        """
        Test retrieval attempt with a non-existent national ID.

        Expected behavior:
            - Status code 404.
            - Return error message indicating user was not found.
        """
        url = reverse("certificates-api:v1:user-certificate-list", args=[1111111111])
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["error"],
            "User with the provided national ID was not found."
        )

    def test_get_certificates_forbidden_non_staff(self):
        """
        Test retrieval attempt by an authenticated non-staff user.

        Expected behavior:
            - Status code 403.
        """
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_certificate_by_certificate_id_forbidden_non_staff(self):
        """
        Test certificate ID retrieval attempt by an authenticated non-staff user.

        Expected behavior:
            - Status code 403.
        """
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_certificates_unauthenticated(self):
        """
        Test retrieval attempt without valid authentication.

        Expected behavior:
            - Status code 401.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificates_logs_caller_audit_without_national_id(self):
        """
        Test that a national ID lookup is audited by type and target, never by value.

        Expected behavior:
            - Status code 200.
            - The audit line names the surface, the caller, the lookup type and the target user id.
            - The national ID is not in the audit line.
        """
        self.client.force_authenticate(user=self.staff_user)
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
                response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('"surface": "certificates.v1.users"', logs.output[0])
        self.assertIn(f'"user_id": {self.staff_user.id}', logs.output[0])
        self.assertIn('"lookup_type": "national_id"', logs.output[0])
        self.assertIn(f'"target_user_id": {self.student.id}', logs.output[0])
        self.assertIn("(?P<national_id>", logs.output[0])
        self.assertNotIn(NATIONAL_ID, logs.output[0])

    def test_get_certificates_forbidden_logs_caller_audit(self):
        """
        Test that a refused caller is audited too.

        Expected behavior:
            - Status code 403.
            - The audit line carries the 403 status and the caller, and no target user id.
        """
        self.client.force_authenticate(user=self.regular_user)

        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('"status": 403', logs.output[0])
        self.assertIn(f'"user_id": {self.regular_user.id}', logs.output[0])
        self.assertNotIn("target_user_id", logs.output[0])

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_non_member_is_logged_while_switch_is_off(self):
        """
        Test a national ID lookup of a person outside the tenant while the switch is off.

        Expected behavior:
            - Status code 200 (unchanged behaviour).
            - The audit line records the would_deny verdict.
        """
        self.member_mock.return_value = False
        self.client.force_authenticate(user=self.staff_user)
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
                response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('"tenant_scope": "would_deny"', logs.output[0])

    @override_waffle_switch(ENFORCE_TENANT_SCOPED_LOOKUPS, True)
    def test_non_member_is_not_found_when_enforced(self):
        """
        Test a national ID lookup of a person outside the tenant once the switch is on.

        Expected behavior:
            - Status code 404 with the same body as an unknown national ID.
            - The audit line records the deny verdict.
        """
        self.member_mock.return_value = False
        self.client.force_authenticate(user=self.staff_user)

        with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "User with the provided national ID was not found.")
        self.assertIn('"tenant_scope": "deny"', logs.output[0])

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    @override_waffle_switch(ENFORCE_TENANT_SCOPED_LOOKUPS, True)
    def test_member_gets_only_tenant_certificates_when_enforced(self):
        """
        Test that a member's certificates of other tenants' orgs are dropped once the switch is on.

        Expected behavior:
            - Status code 200.
            - No certificate is returned when the tenant does not own the certificate's org.
            - The audit line counts the dropped certificate.
        """
        self.tenant_orgs_mock.return_value = {"another-org"}
        self.client.force_authenticate(user=self.staff_user)

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
                response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["certificates"], [])
        self.assertIn('"certificates_outside_tenant": 1', logs.output[0])
        self.assertIn('"tenant_scope": "allow"', logs.output[0])

    @override_waffle_switch(ENFORCE_TENANT_SCOPED_LOOKUPS, True)
    def test_certificate_of_another_tenant_is_not_found_when_enforced(self):
        """
        Test a certificate ID lookup of a certificate of another tenant's org once the switch is on.

        Expected behavior:
            - Status code 404 with the same body as an unknown certificate ID.
        """
        self.tenant_orgs_mock.return_value = {"another-org"}
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "Certificate with the provided certificate ID was not found.")

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    @override_waffle_switch(ENFORCE_TENANT_SCOPED_LOOKUPS, True)
    def test_superuser_keeps_global_lookup(self):
        """
        Test that a superuser still gets every certificate of a person outside the tenant.

        Expected behavior:
            - Status code 200 with the certificate.
            - The audit line records the global scope.
        """
        self.member_mock.return_value = False
        self.tenant_orgs_mock.return_value = {"another-org"}
        self.staff_user.is_superuser = True
        self.staff_user.save()
        self.client.force_authenticate(user=self.staff_user)
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            with self.assertLogs("eox_nelp.audit", level="INFO") as logs:
                response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["certificates"], [self.expected_certificate_data()])
        self.assertIn('"tenant_scope": "global"', logs.output[0])
