"""Request serializer of the enrollment override.

eox-core validates every item BEFORE the view runs, and its `validate` turns an email without an
account into a 400 ("User not found") for the whole request. That is the one check that has to
change for an unknown email to be reservable; every other check (mode, course, org, bundle) stays.
"""
from eox_core.api.v1.serializers import EdxappCourseEnrollmentQuerySerializer
from eox_core.edxapp_wrapper.enrollments import check_edxapp_enrollment_is_valid
from rest_framework import serializers

USER_NOT_FOUND = "User not found"  # eox-core's wording, pinned by tests/test_pins.py


class NelpEnrollmentQuerySerializer(EdxappCourseEnrollmentQuerySerializer):  # pylint: disable=abstract-method
    """eox-core's query serializer, minus 'User not found' for an email-only item."""

    def validate(self, attrs):
        """Run eox-core's checks; an email-only item may name an email that has no account yet."""
        errors = check_edxapp_enrollment_is_valid(**attrs)
        if attrs.get("email") and not attrs.get("username") and not attrs.get("bundle_id"):
            errors = [error for error in errors if error != USER_NOT_FOUND]
        if errors:
            raise serializers.ValidationError(", ".join(errors))
        return attrs
