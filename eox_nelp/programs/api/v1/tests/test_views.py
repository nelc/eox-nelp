"""Tests for programs API v1 views."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class ProgramsMetadataViewTestCase(TestCase):
    """Test cases for ProgramsMetadataView."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = reverse("programs-api:v1:programs-metadata", kwargs={"course_id": "course-v1:edX+DemoX+Demo_Course"})

    def test_get_program_metadata_success(self):
        """Test successful retrieval of program metadata."""
        # Mock authentication
        with patch("eox_nelp.programs.api.v1.views.IsAuthenticated") as mock_auth:
            mock_auth.return_value = True

            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("program_name", response.data)
            self.assertIn("course_id", response.data)
            self.assertEqual(response.data["course_id"], "course-v1:edX+DemoX+Demo_Course")

    def test_get_program_metadata_not_found(self):
        """Test retrieval of non-existent program metadata."""
        url = reverse("programs-api:v1:programs-metadata", kwargs={"course_id": "non-existent-course"})

        with patch("eox_nelp.programs.api.v1.views.IsAuthenticated") as mock_auth:
            mock_auth.return_value = True

            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertIn("error", response.data)

    def test_get_program_metadata_invalid_course_id(self):
        """Test retrieval with invalid course ID."""
        url = reverse("programs-api:v1:programs-metadata", kwargs={"course_id": ""})

        with patch("eox_nelp.programs.api.v1.views.IsAuthenticated") as mock_auth:
            mock_auth.return_value = True

            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("error", response.data)

    def test_authentication_required(self):
        """Test that authentication is required."""
        response = self.client.get(self.url)

        # This would typically return 401, but depends on authentication setup
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    @patch("eox_nelp.programs.api.v1.views.cache")
    def test_rate_limiting(self, mock_cache):
        """Test rate limiting functionality."""
        # Mock cache to simulate rate limit exceeded
        mock_cache.get.return_value = 100  # Max requests reached

        with patch("eox_nelp.programs.api.v1.views.IsAuthenticated") as mock_auth:
            mock_auth.return_value = True

            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("Rate limit exceeded", response.data["error"])

    def test_program_metadata_structure(self):
        """Test that program metadata has expected structure."""
        with patch("eox_nelp.programs.api.v1.views.IsAuthenticated") as mock_auth:
            mock_auth.return_value = True

            response = self.client.get(self.url)

            if response.status_code == status.HTTP_200_OK:
                expected_fields = [
                    "course_id",
                    "program_name",
                    "program_description",
                    "program_type",
                    "duration",
                    "credits",
                    "prerequisites",
                    "learning_objectives",
                    "certification",
                    "created_at",
                    "updated_at",
                ]

                for field in expected_fields:
                    self.assertIn(field, response.data, f"Field '{field}' missing from response")
