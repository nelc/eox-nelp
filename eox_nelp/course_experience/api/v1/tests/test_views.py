"""This file contains all the test for the course_experience views.py file.
Classes:
    LikeDislikeUnitExperienceTestCase: Test LikeDislikeUnitExperienceView.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.course_experience.models import (
    FeedbackCourse,
    LikeDislikeCourse,
    LikeDislikeUnit,
    ReportCourse,
    ReportUnit,
)
from eox_nelp.course_experience.cache import upsert_experience_cache
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview

from .mixins_helpers import (
    BASE_COURSE_ID,
    BASE_ITEM_ID,
    CourseExperienceTestMixin,
    FeedbackPublicExperienceTestMixin,
    UnitExperienceTestMixin,
)


class LikeDislikeUnitExperienceTestCase(UnitExperienceTestMixin, APITestCase):
    """ Test LikeDislikeUnitExperience view """

    reverse_viewname_list = "course-experience-api:v1:like-units-list"
    reverse_viewname_detail = "course-experience-api:v1:like-units-detail"
    object_key = "item_id"
    patch_data = {"status": True}
    post_data = {
        "item_id": "block-v1:edX+cd1011+2020t1+type@vertical+block@new_item2",
        "status": False,
        "course_id": {
            "type": "CourseOverview",
            "id": f"{BASE_COURSE_ID}",
        }
    }

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(LikeDislikeUnitExperienceTestCase).
        """
        super().setUp()
        self.my_unit_like, _ = LikeDislikeUnit.objects.get_or_create(  # pylint: disable=no-member
            item_id=BASE_ITEM_ID,
            course_id=self.my_course,
            author_id=self.user.id,
            status=False,
        )
        upsert_experience_cache("LikeDislikeUnit", self.user.id, BASE_ITEM_ID, {
            "status": self.my_unit_like.status,
            "course_id": str(self.my_course.id),
        })
        self.base_data = {
            "data": {
                "type": "LikeDislikeUnit",
                "id": f"{self.my_unit_like.id}",
                "attributes": {
                    "username": f"{self.user.username}",
                    "status": self.my_unit_like.status,
                    "item_id": f"{self.my_unit_like.item_id}",
                },
                "relationships": self.make_relationships_data()
            }
        }
        self.object_url_kwarg = {self.object_key: BASE_ITEM_ID}


class ReportUnitExperienceTestCase(UnitExperienceTestMixin, APITestCase):
    """ Test ReportUnitExperience view """

    reverse_viewname_list = "course-experience-api:v1:report-units-list"
    reverse_viewname_detail = "course-experience-api:v1:report-units-detail"
    object_key = "item_id"
    patch_data = {"reason": "HA"}
    post_data = {
        "item_id": "block-v1:edX+cd1011+2020t1+type@vertical+block@new_item",
        "reason": "OO",
        "course_id": {
            "type": "CourseOverview",
            "id": f"{BASE_COURSE_ID}"
        }
    }

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(ReportUnitExperienceTestCase).
        """
        super().setUp()
        self.my_unit_report, _ = ReportUnit.objects.get_or_create(  # pylint: disable=no-member
            item_id=BASE_ITEM_ID,
            course_id=self.my_course,
            author_id=self.user.id,
            reason="Sexual content",
        )
        upsert_experience_cache("ReportUnit", self.user.id, BASE_ITEM_ID, {
            "reason": self.my_unit_report.reason,
            "course_id": str(self.my_course.id),
        })
        self.base_data = {
            "data": {
                "type": "ReportUnit",
                "id": f"{self.my_unit_report.id}",
                "attributes": {
                    "username": f"{self.user.username}",
                    "reason": f"{self.my_unit_report.reason}",
                    "item_id": f"{self.my_unit_report.item_id}",
                },
                "relationships": self.make_relationships_data()
            }
        }
        self.object_url_kwarg = {self.object_key: BASE_ITEM_ID}

    def test_post_wrong_reason(self):
        """
        Test a  post request sending a not valid choice reason.
        Expected behavior:
            - Return expected content not valid choice.
            - Status code 404.
        """
        data = self.base_data
        url_endpoint = reverse(self.reverse_viewname_list)
        data["item_id"] = "block-v1:edX+cd1011+2020t1+type@vertical+block@new_item_reason"
        data["reason"] = "not valid choice reason"

        response = self.client.post(url_endpoint, data, format="json", contentType="application/json")

        self.assertContains(response, "is not a valid choice.", status_code=status.HTTP_400_BAD_REQUEST)


class LikeDislikeCourseExperienceTestCase(CourseExperienceTestMixin, APITestCase):
    """ Test LikeDislikeCourseExperience view """

    reverse_viewname_list = "course-experience-api:v1:like-courses-list"
    reverse_viewname_detail = "course-experience-api:v1:like-courses-detail"
    object_key = "course_id"
    new_object_id = "course-v1:edX+cd101+2023-new_course"
    patch_data = {"status": True}
    post_data = {
        "course_id": {
            "type": "CourseOverview",
            "id": f"{new_object_id}"
        },
        "status": True
    }

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(LikeDislikeCourseExperienceTestCase).
        """
        super().setUp()
        self.my_course_like, _ = LikeDislikeCourse.objects.get_or_create(  # pylint: disable=no-member
            course_id=self.my_course,
            author_id=self.user.id,
            status=False,
        )
        upsert_experience_cache("LikeDislikeCourse", self.user.id, str(self.my_course), {
            "status": self.my_course_like.status,
            "course_id": str(self.my_course.id),
        })
        self.object_url_kwarg = {self.object_key: BASE_COURSE_ID}
        # add another course due the post doesnt work without existent courseoverview
        self.my_new_course, _ = CourseOverview.objects.get_or_create(id=self.new_object_id)
        self.base_data = {
            "data": {
                "type": "LikeDislikeCourse",
                "id": f"{self.my_course_like.id}",
                "attributes": {
                    "username": f"{self.user.username}",
                    "status": self.my_course_like.status,
                },
                "relationships": self.make_relationships_data()
            }
        }


class ReportCourseExperienceTestCase(CourseExperienceTestMixin, APITestCase):
    """ Test ReportCourseExperience view """
    reverse_viewname_list = "course-experience-api:v1:report-courses-list"
    reverse_viewname_detail = "course-experience-api:v1:report-courses-detail"
    object_key = "course_id"
    new_object_id = "course-v1:edX+cd101+2023-new_course"
    patch_data = {"reason": "HA"}
    post_data = {
        "course_id": {
            "type": "CourseOverview",
            "id": f"{new_object_id}",
        },
        "reason": "GV",
    }

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(ReportCourseExperienceTestCase).
        """
        super().setUp()
        self.my_course_report, _ = ReportCourse.objects.get_or_create(  # pylint: disable=no-member
            course_id=self.my_course,
            author_id=self.user.id,
            reason="Sexual content",
        )
        upsert_experience_cache("ReportCourse", self.user.id, str(self.my_course), {
            "reason": self.my_course_report.reason,
            "course_id": str(self.my_course.id),
        })
        self.object_url_kwarg = {self.object_key: BASE_COURSE_ID}
        self.my_new_course, _ = CourseOverview.objects.get_or_create(id=self.new_object_id)
        self.base_data = {
            "data": {
                "type": "ReportCourse",
                "id": f"{self.my_course_report.id}",
                "attributes": {
                    "username": f"{self.user.username}",
                    "reason": f"{self.my_course_report.reason}"
                },
                "relationships": self.make_relationships_data()
            }
        }


class FeedbackCourseExperienceTestCase(CourseExperienceTestMixin, APITestCase):
    """ Test FeedbackCourseExperience view """
    reverse_viewname_list = "course-experience-api:v1:feedback-courses-list"
    reverse_viewname_detail = "course-experience-api:v1:feedback-courses-detail"
    object_key = "course_id"
    new_object_id = "course-v1:edX+cd101+2023-new_course"
    patch_data = {
        "rating_content": 0,
        "rating_instructors": 3,
        "public": True,
        "recommended": False
    }
    post_data = {
        "course_id": {
            "type": "CourseOverview",
            "id": f"{new_object_id}",
        },
        "feedback": "this is new feedback",
        "rating_content": 4,
        "rating_instructors": 3,
        "public": True,
        "recommended": False,
    }

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(FeedbackCourseExperienceTestCase).
        """
        super().setUp()
        self.my_course_feedback, _ = FeedbackCourse.objects.get_or_create(  # pylint: disable=no-member
            course_id=self.my_course,
            author_id=self.user.id,
            feedback="legacy created feedback",
            rating_content=4,
            rating_instructors=3,
            public=True,
            recommended=False,
        )
        upsert_experience_cache("FeedbackCourse", self.user.id, str(self.my_course), {
            "feedback": self.my_course_feedback.feedback,
            "rating_content": self.my_course_feedback.rating_content,
            "rating_instructors": self.my_course_feedback.rating_instructors,
            "public": self.my_course_feedback.public,
            "recommended": self.my_course_feedback.recommended,
        })
        self.object_url_kwarg = {self.object_key: BASE_COURSE_ID}
        self.my_new_course, _ = CourseOverview.objects.get_or_create(id=self.new_object_id)
        self.base_data = {
            "data": {
                "type": "FeedbackCourse",
                "id": f"{self.my_course_feedback.id}",
                "attributes": {
                    "username": f"{self.user.username}",
                    "feedback": f"{self.my_course_feedback.feedback}",
                    "rating_content": self.my_course_feedback.rating_content,
                    "rating_instructors": self.my_course_feedback.rating_instructors,
                    "public": self.my_course_feedback.public,
                    "recommended": self.my_course_feedback.recommended,
                },
                "relationships": self.make_relationships_data()
            }
        }


# -------------------------------------------TEST PUBLIC VIEWS----------------------------------------------------------

class FeedbackPublicCourseExperienceTestCase(FeedbackPublicExperienceTestMixin, APITestCase):
    """Test PublicFeedbackExperience  view"""

    reverse_viewname_list = "course-experience-api:v1:feedback-public-courses-list"
    reverse_viewname_detail = "course-experience-api:v1:feedback-public-courses-detail"
    object_key = "course_id"

    def setUp(self):
        """
        Set variables and objects that depends in other class vars.
        Using self(FeedbackCourseExperienceTestCase).
        """
        super().setUp()
        self.my_course_feedbacks = FeedbackCourse.objects.bulk_create(  # pylint: disable=no-member
            [
                FeedbackCourse(
                    course_id=course_overview_iter,
                    author=user_iter,
                    feedback=f"feedback {user_index} by user {user_iter.username} in course {course_overview_iter.id}",
                    rating_content=user_index,
                    rating_instructors=user_index + 1,
                    public=bool(user_index > 3),
                    recommended=bool(user_index >= 3),
                )
                for course_overview_iter in self.course_overviews
                for user_index, user_iter in enumerate(self.users)
            ],  # create 15 feedbackcourse: 3 course overview with 5 users.
        )

        self.object_url_kwarg = {self.object_key: BASE_COURSE_ID}
