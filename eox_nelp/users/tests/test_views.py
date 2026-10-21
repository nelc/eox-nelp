"""
Test file for users views.
"""
from unittest.mock import patch

from custom_reg_form.models import ExtraInfo
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from eox_nelp.users.api.v1.views import CoreEdxappUser

User = get_user_model()


class NelpEdxappUserTestCase(APITestCase):
    """Test case for NelpEdxappUser view."""

    def setUp(self):
        """Set up test case."""
        self.url = reverse('users:v1:edxapp-user')
        self.client = APIClient()

        # Create admin user for authentication
        self.client_user, _ = User.objects.get_or_create(username='test_admin', password='test123')
        self.client.force_authenticate(self.client_user)
        self.test_user, _ = User.objects.get_or_create(
            username='testuser',
            email='test@example.com',
            defaults={
                'is_active': True,
            },
        )
        self.test_user.extrainfo = ExtraInfo.objects.create(  # pylint: disable=no-member
            user=self.test_user,
            national_id='1234567890',
            arabic_name='اسم عربي',
            arabic_first_name='الاسم الأول',
            arabic_last_name='اسم العائلة',
        )

        # Patch authentication classes
        self.auth_patcher = patch.object(
            CoreEdxappUser,
            'authentication_classes',
            [],
        )
        self.auth_patcher.start()

        # Patch permission classes
        self.perm_patcher = patch.object(
            CoreEdxappUser,
            'permission_classes',
            [],
        )
        self.perm_patcher.start()

    def tearDown(self):
        """Clean up after each test."""
        self.auth_patcher.stop()
        self.perm_patcher.stop()
        super().tearDown()

    @patch('eox_nelp.users.api.v1.views.NelpUserReadOnlySerializer')
    def test_get_user_query_with_username(self, mock_serializer_class):
        """Test get_user_query method with username parameter.

        Expected behavior:
            - Returns 200 status code
            - Response data matches expected serialized user data
            - NelpUserReadOnlySerializer is instantiated once
        """
        serializer_data = {
            'username': self.test_user.username,
            'extrainfo': {'national_id': self.test_user.extrainfo.national_id},
        }
        mock_serializer_class.return_value.data = serializer_data

        response = self.client.get(f"{self.url}?username={self.test_user.username}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer_data)
        mock_serializer_class.assert_called_once()

    @patch('eox_nelp.users.api.v1.views.NelpUserReadOnlySerializer')
    def test_get_user_query_with_email(self, mock_serializer_class):
        """Test get_user_query method with email parameter.

        Expected behavior:
            - Returns 200 status code
            - Response data matches expected serialized user data
            - NelpUserReadOnlySerializer is instantiated once
        """
        serializer_data = {
            'username': self.test_user.username,
            'email': self.test_user.email,
        }
        mock_serializer_class.return_value.data = serializer_data

        response = self.client.get(f"{self.url}?email={self.test_user.email}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer_data)
        mock_serializer_class.assert_called_once()

    @patch('eox_nelp.users.api.v1.views.NelpUserReadOnlySerializer')
    def test_get_user_query_with_national_id(self, mock_serializer_class):
        """Test get_user_query method with national_id parameter.

        Expected behavior:
            - Returns 200 status code
            - Response data matches expected serialized user data
            - NelpUserReadOnlySerializer is instantiated once
        """
        serializer_data = {
            'username': self.test_user.username,
            'extrainfo': {'national_id': self.test_user.extrainfo.national_id},
        }
        mock_serializer_class.return_value.data = serializer_data

        response = self.client.get(f"{self.url}?national_id={self.test_user.extrainfo.national_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer_data)
        mock_serializer_class.assert_called_once()

    def test_get_user_query_no_params(self):
        """Test get_user_query method with no parameters.

        Expected behavior:
            - Returns 400 Bad Request status code
            - Error message indicates missing required parameters
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data[0]), 'Email or username or national_id needed')

    def test_get_user_not_found(self):
        """Test get method when user is not found.

        Expected behavior:
            - Returns 404 Not Found status code
        """
        response = self.client.get(f"{self.url}?username=nonexistent")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('eox_nelp.users.api.v1.views.NelpUserReadOnlySerializer')
    def test_get_logs_caller_audit_without_lookup_value(self, mock_serializer_class):
        """Test that a national_id lookup is audited by type and target, never by value.

        Expected behavior:
            - Returns 200 status code
            - The audit line names the surface, the lookup type and the target user id
            - The national_id value is not in the audit line
        """
        mock_serializer_class.return_value.data = {}

        with self.assertLogs('eox_nelp.audit', level='INFO') as logs:
            response = self.client.get(f"{self.url}?national_id={self.test_user.extrainfo.national_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('"surface": "users.v1.user"', logs.output[0])
        self.assertIn('"lookup_type": "national_id"', logs.output[0])
        self.assertIn(f'"target_user_id": {self.test_user.id}', logs.output[0])
        self.assertNotIn(self.test_user.extrainfo.national_id, logs.output[0])

    def test_get_not_found_logs_caller_audit_without_target(self):
        """Test that a lookup that finds no user is audited with its status and no target.

        Expected behavior:
            - Returns 404 status code
            - The audit line carries the 404 status and the lookup type, and no target user id
        """
        with self.assertLogs('eox_nelp.audit', level='INFO') as logs:
            response = self.client.get(f"{self.url}?username=nonexistent")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('"status": 404', logs.output[0])
        self.assertIn('"lookup_type": "username"', logs.output[0])
        self.assertNotIn('target_user_id', logs.output[0])
        self.assertNotIn('nonexistent', logs.output[0])
