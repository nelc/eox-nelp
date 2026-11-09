"""Tests for the pipeline steps that resolve and sync an SSO login by the asserted national ID."""
from custom_reg_form.models import ExtraInfo
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import HttpResponseForbidden
from django.test import TestCase, override_settings
from mock import Mock, patch

from eox_nelp.third_party_auth import pipeline
from eox_nelp.third_party_auth.utils import get_national_id_claim

User = get_user_model()

BACKEND_NAME = "config-based-openidconnect-PKCE"
ASSOCIATION_SETTING = {
    "SOCIAL_AUTH_CONFIG_BASED_OPENIDCONNECT_PKCE_USER_ASSOCIATION_ATTRIBUTE": {
        "attribute_path": "client_NationalId",
        "user_query": "extrainfo__national_id",
    },
}
CLAIM = "1043822608"
CLAIM_ARABIC_INDIC = "١٠٤٣٨٢٢٦٠٨"
OTHER_VALID_ID = "1098538166"
INVALID_CHECK_DIGIT_ID = "1043822609"


class NationalIdClaimMixin:
    """Common objects for the national ID claim pipeline tests."""

    def setUp(self):  # pylint: disable=invalid-name
        """Create a backend, a request and an IdP response asserting CLAIM."""
        self.backend = Mock()
        self.backend.name = BACKEND_NAME
        self.request = Mock()
        self.response = {"client_NationalId": CLAIM, "client_Email": "learner@example.com"}

    @staticmethod
    def create_user(username, national_id=None, email=""):
        """Create a user with an ExtraInfo row holding national_id."""
        user = User.objects.create(username=username, email=email)
        ExtraInfo.objects.create(user=user, national_id=national_id, arabic_name="متعلم")  # pylint: disable=no-member

        return user


@override_settings(**ASSOCIATION_SETTING)
class GetNationalIdClaimTestCase(NationalIdClaimMixin, TestCase):
    """Tests for get_national_id_claim."""

    def test_valid_claim(self):
        """A valid claim is returned as it was sent."""
        self.assertEqual(get_national_id_claim(self.backend, self.response), CLAIM)

    def test_arabic_indic_and_numeric_claims_are_normalized(self):
        """Arabic-Indic digits and an integer claim give the ASCII string."""
        self.assertEqual(get_national_id_claim(self.backend, {"client_NationalId": CLAIM_ARABIC_INDIC}), CLAIM)
        self.assertEqual(get_national_id_claim(self.backend, {"client_NationalId": int(CLAIM)}), CLAIM)

    def test_invalid_check_digit_is_ignored(self):
        """A claim with a wrong check digit is treated as absent."""
        self.assertEqual(get_national_id_claim(self.backend, {"client_NationalId": INVALID_CHECK_DIGIT_ID}), "")

    def test_missing_claim(self):
        """No claim in the response gives an empty string."""
        self.assertEqual(get_national_id_claim(self.backend, {}), "")

    @override_settings(SOCIAL_AUTH_CONFIG_BASED_OPENIDCONNECT_PKCE_USER_ASSOCIATION_ATTRIBUTE=None)
    def test_backend_without_setting(self):
        """A backend without the association setting asserts no national ID."""
        self.assertEqual(get_national_id_claim(self.backend, self.response), "")


@override_settings(**ASSOCIATION_SETTING)
@patch("eox_nelp.third_party_auth.pipeline.logout")
class RefuseLinkedUserWithOtherNationalIdTestCase(NationalIdClaimMixin, TestCase):
    """Tests for refuse_linked_user_with_other_national_id."""

    def run_step(self, user):
        """Run the step for the linked user."""
        return pipeline.refuse_linked_user_with_other_national_id(
            self.request, self.backend, self.response, user=user,
        )

    def test_other_valid_national_id_is_refused(self, logout_mock):
        """The account of another person is never logged in: session closed, 403 page."""
        user = self.create_user("person_a", OTHER_VALID_ID)

        result = self.run_step(user)

        self.assertIsInstance(result, HttpResponseForbidden)
        logout_mock.assert_called_once_with(self.request)

    def test_matching_national_id_continues(self, logout_mock):
        """The account holding the asserted national ID continues, also when stored with Arabic-Indic digits."""
        for username, stored in (("same", CLAIM), ("arabic", CLAIM_ARABIC_INDIC)):
            with self.subTest(stored=stored):
                ExtraInfo.objects.filter(national_id=CLAIM).delete()  # pylint: disable=no-member
                self.assertEqual(self.run_step(self.create_user(username, stored)), {})
        logout_mock.assert_not_called()

    def test_empty_or_invalid_stored_national_id_continues(self, logout_mock):
        """An empty or invalid stored value is left for the sync step to correct."""
        self.assertEqual(self.run_step(self.create_user("empty")), {})
        self.assertEqual(self.run_step(self.create_user("typo", INVALID_CHECK_DIGIT_ID)), {})
        logout_mock.assert_not_called()

    def test_no_user_or_no_claim_continues(self, logout_mock):
        """Without a linked user or an asserted national ID there is nothing to compare."""
        self.assertEqual(self.run_step(None), {})
        self.response = {}
        self.assertEqual(self.run_step(self.create_user("person_a", OTHER_VALID_ID)), {})
        logout_mock.assert_not_called()


@override_settings(**ASSOCIATION_SETTING)
class AssociateUserByNationalIdClaimTestCase(NationalIdClaimMixin, TestCase):
    """Tests for associate_user_by_national_id_claim."""

    def run_step(self, user=None):
        """Run the step."""
        return pipeline.associate_user_by_national_id_claim(self.backend, self.response, user=user)

    def test_single_holder_is_associated(self):
        """The only account holding the asserted national ID is the pipeline user."""
        holder = self.create_user("holder", CLAIM)

        self.assertEqual(self.run_step(), {"user": holder, "is_new": False})

    def test_arabic_indic_stored_holder_is_associated(self):
        """A legacy row stored with Arabic-Indic digits is matched as well."""
        holder = self.create_user("holder", CLAIM_ARABIC_INDIC)

        self.assertEqual(self.run_step(), {"user": holder, "is_new": False})

    def test_two_holders_are_not_associated(self):
        """Two accounts holding both forms of the national ID are ambiguous, nothing is associated."""
        self.create_user("ascii", CLAIM)
        self.create_user("arabic", CLAIM_ARABIC_INDIC)

        self.assertIsNone(self.run_step())

    def test_no_holder_and_matched_user(self):
        """No holder, an invalid claim or an already matched user leave the pipeline unchanged."""
        self.assertIsNone(self.run_step())
        self.assertIsNone(self.run_step(user=self.create_user("matched")))
        self.response = {"client_NationalId": INVALID_CHECK_DIGIT_ID}
        self.create_user("typo", INVALID_CHECK_DIGIT_ID)
        self.assertIsNone(self.run_step())

    def test_email_is_never_used(self):
        """An account with the asserted email but another national ID is not associated."""
        self.create_user("person_a", OTHER_VALID_ID, email="learner@example.com")

        self.assertIsNone(self.run_step())


@patch("eox_nelp.third_party_auth.pipeline.logout")
class RefuseUnmatchedEmailConflictTestCase(NationalIdClaimMixin, TestCase):
    """Tests for refuse_unmatched_email_conflict."""

    def test_taken_email_is_refused(self, logout_mock):
        """No matched account and the email belongs to an account (any case): session closed, 403 page."""
        self.create_user("person_a", OTHER_VALID_ID, email="Learner@Example.com")

        result = pipeline.refuse_unmatched_email_conflict(self.request, {"email": "learner@example.com"})

        self.assertIsInstance(result, HttpResponseForbidden)
        logout_mock.assert_called_once_with(self.request)

    def test_free_email_or_matched_user_continues(self, logout_mock):
        """A free email, no email or a matched user continue to the account creation."""
        user = self.create_user("person_a", OTHER_VALID_ID, email="learner@example.com")

        self.assertEqual(pipeline.refuse_unmatched_email_conflict(self.request, {"email": "new@example.com"}), {})
        self.assertEqual(pipeline.refuse_unmatched_email_conflict(self.request, {}), {})
        self.assertEqual(
            pipeline.refuse_unmatched_email_conflict(self.request, {"email": "learner@example.com"}, user=user), {},
        )
        logout_mock.assert_not_called()


@override_settings(**ASSOCIATION_SETTING)
class SyncNationalIdFromClaimTestCase(NationalIdClaimMixin, TestCase):
    """Tests for sync_national_id_from_claim."""

    def run_step(self, user):
        """Run the step and return the national_id stored for the user afterwards."""
        self.assertEqual(pipeline.sync_national_id_from_claim(self.backend, self.response, user=user), {})

        return ExtraInfo.objects.get(user=user).national_id  # pylint: disable=no-member

    def test_empty_stored_value_is_filled(self):
        """An account without a national ID gets the asserted one."""
        self.assertEqual(self.run_step(self.create_user("empty")), CLAIM)

    def test_missing_extrainfo_is_created(self):
        """An account without an ExtraInfo row gets one holding the asserted national ID."""
        self.assertEqual(self.run_step(User.objects.create(username="no_extrainfo")), CLAIM)

    def test_invalid_or_arabic_indic_stored_value_is_replaced(self):
        """A typo (wrong check digit) or the Arabic-Indic form is replaced by the asserted national ID."""
        self.assertEqual(self.run_step(self.create_user("typo", INVALID_CHECK_DIGIT_ID)), CLAIM)
        ExtraInfo.objects.filter(national_id=CLAIM).delete()  # pylint: disable=no-member
        self.assertEqual(self.run_step(self.create_user("arabic", CLAIM_ARABIC_INDIC)), CLAIM)

    def test_other_valid_stored_value_is_kept(self):
        """A different valid national ID is never overwritten."""
        self.assertEqual(self.run_step(self.create_user("person_a", OTHER_VALID_ID)), OTHER_VALID_ID)

    def test_national_id_held_by_another_account_is_not_copied(self):
        """The asserted national ID is not written when another account holds it."""
        self.create_user("holder", CLAIM_ARABIC_INDIC)

        self.assertEqual(self.run_step(self.create_user("typo", INVALID_CHECK_DIGIT_ID)), INVALID_CHECK_DIGIT_ID)

    def test_invalid_claim_or_no_user_changes_nothing(self):
        """An invalid claim writes nothing, and no user is a no-op."""
        self.assertEqual(pipeline.sync_national_id_from_claim(self.backend, self.response, user=None), {})
        self.response = {"client_NationalId": INVALID_CHECK_DIGIT_ID}
        self.assertIsNone(self.run_step(self.create_user("empty")))

    def test_concurrent_write_is_logged(self):
        """A unique-constraint race is logged and the login continues."""
        user = self.create_user("empty")

        with patch.object(ExtraInfo, "save", side_effect=IntegrityError), self.assertLogs(pipeline.logger, "WARNING"):
            self.assertEqual(pipeline.sync_national_id_from_claim(self.backend, self.response, user=user), {})
