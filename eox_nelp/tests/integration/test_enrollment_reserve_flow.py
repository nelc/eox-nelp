"""Integration plan for the reserve flow. NOT RUN: needs a real LMS database and the registration signal.

Skipped on purpose (never faked). Run it in the built image / local Tutor with the real edx-platform:

1. POST /eox-core/api/v1/enrollment/ {"email": "new@example.com", "course_id": <open course>, "mode": "honor"}
   -> 200, item result "reserved"; a CourseEnrollmentAllowed row (auto_enroll=True) exists; no User row.
2. Register that email through the normal flow, then activate (ADR 0001 risk: SSO / national-ID flows create
   users already active; `user_post_save_callback` only fires when `is_active` or `email` changes).
   -> a CourseEnrollment (is_active=True) exists for the new user and the CEA is linked to the user.
3. Repeat step 1 -> still "reserved"/"enrolled" with no second mail queued (check the broker / mail outbox).
4. Close the course (enrollment_end in the past) and repeat with another email -> item error "Enrollment closed",
   no CEA row.
5. Mail: the queued message is rendered under the caller's tenant (logo, course link) - check the EML in the outbox.
"""
import pytest


@pytest.mark.skip(reason="needs a real LMS DB + registration signal; see module docstring (NOT RUN)")
def test_reserve_then_register_auto_enrols():
    """Reserve, register, and expect the platform to enrol the new account."""
