"""Tests for eox_nelp.profile_image_patches."""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from mock import patch
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from eox_nelp import profile_image_patches
from eox_nelp.profile_image_patches import patch_profile_image_throttle
from eox_nelp.profile_image_throttle import DEFAULT_PROFILE_IMAGE_THROTTLE_RATE, ProfileImageRateThrottle

User = get_user_model()


def make_view(**attributes):
    """Return a fresh APIView subclass that answers every POST with 200."""
    attributes.setdefault("post", lambda self, request: Response({}))
    return type("FakeProfileImageView", (APIView,), {"authentication_classes": (), **attributes})


class ProfileImageRateThrottleTestCase(TestCase):
    """Test ProfileImageRateThrottle."""

    def setUp(self):
        cache.clear()
        self.view = make_view(throttle_classes=(ProfileImageRateThrottle,)).as_view()

    def post(self, user):
        """Send one POST as `user` and return the status code."""
        request = APIRequestFactory().post("/api/user/v1/accounts/someone/image")
        force_authenticate(request, user=user)
        return self.view(request).status_code

    def test_default_rate(self):
        """Without the setting the rate is the module default."""
        self.assertEqual(ProfileImageRateThrottle().get_rate(), DEFAULT_PROFILE_IMAGE_THROTTLE_RATE)

    @override_settings(EOX_NELP_PROFILE_IMAGE_THROTTLE_RATE="2/minute")
    def test_requests_over_the_rate_get_429(self):
        """The third request in the window is refused, for that user only.

        Expected behavior:
            - The first two requests of a user pass.
            - The third gets 429.
            - Another user is not affected.
        """
        user, other_user = User.objects.create(username="uploader"), User.objects.create(username="other")

        self.assertEqual([self.post(user), self.post(user), self.post(user)], [200, 200, 429])
        self.assertEqual(self.post(other_user), 200)


class PatchProfileImageThrottleTestCase(TestCase):
    """Test patch_profile_image_throttle."""

    def test_views_without_throttle_get_it(self):
        """Every profile image view with no throttle gets ProfileImageRateThrottle."""
        views = SimpleNamespace(
            ProfileImageView=make_view(),
            ProfileImageUploadView=make_view(),
            ProfileImageRemoveView=make_view(),
        )

        with patch.object(profile_image_patches, "import_module", return_value=views) as import_module_mock:
            patch_profile_image_throttle()

        import_module_mock.assert_called_once_with("openedx.core.djangoapps.profile_images.views")
        for view in (views.ProfileImageView, views.ProfileImageUploadView, views.ProfileImageRemoveView):
            self.assertEqual(view.throttle_classes, (ProfileImageRateThrottle,))

    def test_view_with_its_own_throttle_is_kept(self):
        """A view that already declares a throttle is not changed, and a missing view is logged."""
        views = SimpleNamespace(ProfileImageView=make_view(throttle_classes=(AnonRateThrottle,)))

        with patch.object(profile_image_patches, "import_module", return_value=views):
            with self.assertLogs(profile_image_patches.logger, level="WARNING") as logs:
                patch_profile_image_throttle()

        self.assertEqual(views.ProfileImageView.throttle_classes, (AnonRateThrottle,))
        self.assertEqual(len(logs.output), 2)

    def test_platform_not_installed(self):
        """Nothing happens when edx-platform cannot be imported."""
        with patch.object(profile_image_patches, "import_module", side_effect=ImportError):
            patch_profile_image_throttle()
