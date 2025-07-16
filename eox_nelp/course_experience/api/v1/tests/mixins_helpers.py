"""This file contains mixins to use for experience views test cases.
Mixins:
    - ExperienceTestMixin.
    - UnitExperienceTestMixin
    - CourseExperienceTestMixin
"""
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from mock import patch
from rest_framework import status
from rest_framework.test import APIClient

from eox_nelp.course_experience.api.v1.serializers import get_course_extra_attributes, get_user_extra_attributes
from eox_nelp.course_experience.api.v1.views import INVALID_KEY_ERROR
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview

User = get_user_model()

RESPONSE_CONTENT_TYPES = ["application/vnd.api+json", "application/json"]
BASE_ITEM_ID = "block-v1:edX+cd1011+2020t1+type@vertical+block@base_item"
BASE_COURSE_ID = "course-v1:edX+cd101+2023-t2"


class ExperienceTestMixin:
    """
    A mixin class with base experience setup configuration for testing.
    """
    def setUp(self):  # pylint: disable=invalid-name
        """
        Set base variables and objects across experience test cases.
        """
        self.client = APIClient()
        self.user, _ = User.objects.get_or_create(username="vader")
        self.my_course, _ = CourseOverview.objects.get_or_create(id=BASE_COURSE_ID)
        self.client.force_authenticate(self.user)

    def make_relationships_data(self):
        """
        Make the relationships dict with custom extra attributes based in the attributes of the serializers
        withe variables COURSE_OVERVIEW_EXTRA_ATTRIBUTES and USER_EXTRA_ATTRIBUTES

        Returns:
            dict: relationships dict with the corresponding shape, and key-values.
        """
        return {
            "author": {
                "data": {
                    "type": "User",
                    "id": f"{self.user.id}",
                    **get_user_extra_attributes(self.user)
                }
            },
            "course_id": {
                "data": {
                    "type": "CourseOverview",
                    "id": f"{self.my_course.id}",
                    **get_course_extra_attributes(self.my_course)
                }
            },
        }

    def test_get_object_list_by_user(self):
        """ Test a  get  request to the list endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Return a json list  with at least one object.
        """
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['data'])
        for element in response.json()['data']:
            self.assertEqual(element["attributes"]["username"], self.user.username)
            self.assertEqual(element["relationships"]["author"]["data"]["id"], str(self.user.id))

    @override_settings()
    def test_get_relationships_keys_mapped_for_settings(self):
        """ Test the course experiences api returns the keys configured via the
        COURSE_EXPERIENCE_SETTINGS` in settings.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Check all the elements have the relationship attrs keys presented for course according setting config.
            - Check all the elements have the relationship attrs keys for user(author) according setting config.

        """
        url_endpoint = reverse(self.reverse_viewname_list)
        test_course_experience_settings = {
            "COURSE_OVERVIEW_EXTRA_FIELD_MAPPING": {
                "ultra_name": "courseultra",
                "course_key": "instance__field",
            },
            "USER_EXTRA_FIELD_MAPPING": {
                "mega_name": "userultra",
                "user_key": "user__field",
            }
        }
        setattr(settings, "COURSE_EXPERIENCE_SETTINGS", test_course_experience_settings)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['data'])
        for element in response.json()['data']:
            self.assertEqual(
                element["relationships"]["course_id"]["data"]["attributes"].keys(),
                test_course_experience_settings["COURSE_OVERVIEW_EXTRA_FIELD_MAPPING"].keys(),
            )
            self.assertEqual(
                element["relationships"]["author"]["data"]["attributes"].keys(),
                test_course_experience_settings["USER_EXTRA_FIELD_MAPPING"].keys(),
            )

    def test_not_authenticated_user(self):
        """
        Test disallow by credentials the  get  request to the list endpoint
         for the desired view.
        Expected behavior:
            - Return expected content.
            - Status code 401.
        """
        self.client.force_authenticate(user=None)
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertContains(
            response, "Authentication credentials were not provided",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    def test_patch_object_json(self):
        """
        Test a  patch  request to the detail endpoint for the desired view
        using form data (type xhr in browser).
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Check the response is equal to the expected patched.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)
        expected_data = self.base_data.copy()
        expected_data["data"]["attributes"].update(self.patch_data)

        response = self.client.patch(url_endpoint, self.patch_data, format="json")
        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), expected_data)

    def test_patch_object_form_data(self):
        """
        Test a  patch  request to the detail endpoint for the desired view
        using form data (type document in browser).
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Check the response is equal to the expected patched.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)
        expected_data = self.base_data.copy()
        expected_data["data"]["attributes"].update(self.patch_data)

        response = self.client.patch(url_endpoint, self.patch_data, format="multipart")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), expected_data)

    def test_block_url_object_regex(self):
        """
        Test block a request to the detail endpoint for the desired view
        if the object_id passed Using the  url doesnt match url regex.
        Expected behavior:
            - Return expected content type.
            - Status code 404.
        """
        raw_url_endpoint = f"{reverse(self.reverse_viewname_list)}wrong-regex"

        response = self.client.get(raw_url_endpoint)

        self.assertIn(response.headers["Content-Type"], ["text/html; charset=utf-8"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UnitExperienceTestMixin(ExperienceTestMixin):
    """
    A mixin class with test to use  for testing UnitExperience Views.
    """

    def test_get_specific_item_id(self):
        """
        Test a  get  request to the detail endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Match the response of item_id is eqal to the expected.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), self.base_data)

    def test_get_wrong_item_id(self):
        """
        Test a  get  request to the detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Status code 404.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs={self.object_key: "block-v1:wrong_shape"})

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_not_found_item_id(self):
        """
        Test a  get  request with good shape but the item doesnt exist.
        Using the  detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Status code 404.
            - Return expected msg of Not found  in content.
        """
        url_endpoint = reverse(
            self.reverse_viewname_detail,
            kwargs={
                self.object_key: "block-v1:edX+cd1011+2020t1+type@vertical+block@not_exist"
            },
        )

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertContains(
            response,
            f"No {self.base_data.get('data').get('type')} matches the given query.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    def test_post_item_id(self):
        """
        Test a  post  request to the list endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 201.
            - Check the response object item_id has the expected attributes field.
            - Check the response object item_id has the expected relationships field.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        expected_data = self.base_data.copy()
        expected_data["data"]["attributes"].update(
            {key: value for key, value in self.post_data.items() if key != "course_id"}
        )

        response = self.client.post(url_endpoint, self.post_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["data"]["attributes"], expected_data["data"]["attributes"])
        self.assertEqual(response.json()["data"]["relationships"], expected_data["data"]["relationships"])

    def test_post_wrong_course_id_object(self):
        """
        Test a  post  request with wrong course_id  object.
        Using the  detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Return expected msg of Incorrect type for course_id object in content.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        wrong_data = self.post_data.copy()
        wrong_data["course_id"] = "wrong-course"

        response = self.client.post(url_endpoint, wrong_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertContains(
            response,
            "Incorrect type. Expected resource identifier object, received str.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def test_post_wrong_course_id(self):
        """
        Test a  post  request with wrong course_id string  but good shape object,
        Using the  detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Return expected msg of wrong shape of  `INVALID_KEY_ERROR`.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        wrong_data = self.post_data.copy()
        wrong_data["course_id"]["id"] = "wrong-course-id"

        response = self.client.post(url_endpoint, wrong_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.data, INVALID_KEY_ERROR)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_not_found_course_id(self):
        """
        Test a  post  request with good course_id string, good shape object,
        but courseoverview not exist.
        Using the  detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Return expected msg of oject does not exist in content.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        url_endpoint = reverse(self.reverse_viewname_list)
        wrong_data = self.post_data.copy()
        wrong_data["course_id"]["id"] = "course-v1:edX+cd101+2023-noexist"

        response = self.client.post(url_endpoint, wrong_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertContains(response, "object does not exist.", status_code=status.HTTP_400_BAD_REQUEST)

    def test_patch_wrong_course_id(self):
        """
        Test a  patch  request with wrong course_id string, good shape object.
        Using the  detail endpoint for units views.
        Expected behavior:
            - Return expected content type.
            - Return expected INVALID_KEY_ERROR.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)
        wrong_patch_data = self.patch_data.copy()
        wrong_patch_data["course_id"] = {
            "type": "CourseOverview",
            "id": "wrong-course-id",
        }

        response = self.client.patch(url_endpoint, wrong_patch_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.data, INVALID_KEY_ERROR)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CourseExperienceTestMixin(ExperienceTestMixin):
    """
    A mixin class with test to use  for testing CourseExperience Views.
    """

    def test_get_specific_course_id(self):
        """
        Test a  get  request to the detail endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Match the response object_key with the object_id passed Using the  url.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)

        response = self.client.get(url_endpoint)
        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), self.base_data)

    def test_get_wrong_course_id(self):
        """
        Test a  get  request to the detail endpoint for courses views.
        Expected behavior:
            - Return expected content type.
            - Status code 400.
            - Return expected msg of wrong course_key in content.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs={self.object_key: "course-v1:wrong_shape"})

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_not_found_course_id(self):
        """
        Test a  get  request to the detail endpoint for courses views.
        Expected behavior:
            - Return expected content type.
            - Status code 404.
            - Return expected msg of not found in content.
        """
        url_endpoint = reverse(
            self.reverse_viewname_detail,
            kwargs={self.object_key: "course-v1:edX+cd101+2023-not_exist"},
        )

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertContains(
            response,
            f"No {self.base_data.get('data').get('type')} matches the given query.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    def test_post_course_id(self):
        """
        Test a  post  request to the list endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 201.
            - Check the response object of course_id has the expected attributes field.
            - Check the response object of course_id has the expected relationships field.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        expected_data = self.base_data.copy()
        expected_data["data"]["attributes"].update(
            {key: value for key, value in self.post_data.items() if key != "course_id"}
        )
        expected_data["data"]["relationships"]["course_id"]["data"]["id"] = self.post_data["course_id"]["id"]

        response = self.client.post(url_endpoint, self.post_data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["data"]["attributes"], expected_data["data"]["attributes"])
        self.assertEqual(response.json()["data"]["relationships"], expected_data["data"]["relationships"])

    def test_post_not_found_course_id(self):
        """
        Test a  post  request to the detail endpoint for courses views.
        Expected behavior:
            - Return expected content type.
            - Status code 400.
            - Return expected msg of object associated doesnt exist in content.
        """
        url_endpoint = reverse(self.reverse_viewname_list)
        data = self.post_data
        data["course_id"] = {
            "type": "CourseOverview",
            "id": "course-v1:edX+cd101+2023-not_exist"
        }

        response = self.client.post(url_endpoint, data, format="json", contentType="application/json")

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertContains(response, "object does not exist.", status_code=status.HTTP_400_BAD_REQUEST)


class PublicExperienceTestMixin:
    """
    A mixin class with base experience setup configuration for testing.
    """

    def setUp(self):  # pylint: disable=invalid-name
        """
        Set base variables and objects across experience test cases.
        """
        self.patchers = [
            patch("eox_nelp.course_experience.api.v1.views.configuration_helpers"),
        ]
        self.configuration_helpers_mock = self.patchers[0].start()
        self.configuration_helpers_mock.get_current_site_orgs.return_value = ["org1"]

        self.client = APIClient()
        self.users = User.objects.bulk_create(
            [
                User(username="luke", is_superuser=True, id=1000),
                User(username="han", id=1001),
                User(username="chewi", id=1002),
                User(username="citripio", id=1003),
                User(username="R2D2", id=1004),
            ]
        )
        self.course_overviews = CourseOverview.objects.bulk_create(
            [
                CourseOverview(id="course-v1:org1+multiple+2023-t1", org="org1"),
                CourseOverview(id="course-v1:org1+multiple+2023-t2", org="org1"),
                CourseOverview(id="course-v1:org2+multiple2+2023-t2", org="org2"),
            ]
        )
        self.client.force_authenticate(self.users[0])  # superuser default

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop patching."""
        for patcher in self.patchers:
            patcher.stop()

    def test_post_not_allowed(self):
        """
        Test disallow by credentials the  get  request to the list endpoint
         for the desired view.
        Expected behavior:
            - Status code 405.
        """
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.post(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_specific_not_allowed(self):
        """
        Test disallow by credentials the  get  request to the list endpoint
         for the desired view.
        Expected behavior:
            - Status code 404.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_object_not_allowed(self):
        """
        Test disallow patch.
        Expected behavior:
            - Status code 405.
        """
        url_endpoint = reverse(self.reverse_viewname_detail, kwargs=self.object_url_kwarg)

        response = self.client.patch(url_endpoint, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_list_normal_user(self):
        """Test a  get  request to the list endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects in data list are all public.
        """
        self.client.force_authenticate(user=self.users[1])
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["public"], True)

    def test_get_list_admin_user(self):
        """Test a  get  request to the list endpoint for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Return a json list  with at least one object.
            - Return at least one object in data list with public=False due admin could look it.
        """
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        self.assertIn(False, [element["attributes"]["public"] for element in response.json()["data"]])

    def test_not_authenticated_user(self):
        """
        Test allow without user auth  the  get  request to the list endpoint
        for the desired view.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects are all public.
        """
        self.client.force_authenticate(user=None)
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["public"], True)

    def test_tenant_org_aware(self):
        """
        Test the objects returned are all belonging to course overview with org=org1
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Check returned course_id, are related to a model with only relation of org=org1.
        """
        url_endpoint = reverse(self.reverse_viewname_list)

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        course_overviews_related = [
            CourseOverview.objects.get(id=element["relationships"]["course_id"]["data"]["id"])
            for element in response.json()["data"]
        ]
        for course_overview in course_overviews_related:
            self.assertEqual(course_overview.org, "org1")


class FeedbackPublicExperienceTestMixin(PublicExperienceTestMixin):
    """
    A mixin class with test to use  for Public Feedback CourseExperience Views.
    """
    def test_filter_by_author(self):
        """
        Test the objects returned are filtered by author relationship using username field.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects are related only to the relation username with test_author.
        """
        test_author = "chewi"
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[author.username]={test_author}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["username"], test_author)

    def test_filter_by_course_id(self):
        """
        Test the objects returned are filtered by course_id relationship using id field.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects are related only to the relation course_id with test_course_id.
        """
        test_course_id = str(self.course_overviews[0].id)
        percent_encode_course_id = quote(test_course_id, safe="")  # change `+` to `%2b`
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[course_id.id]={percent_encode_course_id}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["relationships"]["course_id"]["data"]["id"], test_course_id)

    def test_filter_by_rating_content(self):
        """
        Test the objects returned are filtered by rating_content attribute.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects have attribute rating_content matched with  test_rating_content.
        """
        test_rating_content = 3
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[rating_content]={test_rating_content}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["rating_content"], test_rating_content)

    def test_filter_by_rating_instructors(self):
        """
        Test the objects returned are filtered by rating_instructors attribute.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects have attribute rating_instructors matched with  test_rating_intructors.
        """
        test_rating_instructors = 2
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[rating_instructors]={test_rating_instructors}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["rating_instructors"], test_rating_instructors)

    def test_filter_by_recommended(self):
        """
        Test the objects returned are filtered by recommended attribute.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects have attribute recommended matched with test_recommended.
        """
        test_recommended = False
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[recommended]={test_recommended}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["recommended"], test_recommended)

    def test_filter_by_public_admin(self):
        """
        Test the objects returned are filtered by public attribute only with superuser default user.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects have attribute public matched with test_public.
        """
        test_public = False
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[public]={test_public}"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["public"], test_public)

    def test_get_list_normal_user_filter_not_public(self):
        """Test a  get  request to the list endpoint with public false query param but is not superuser.
        Expected behavior:
            - Return expected content type.
            - Status code 200.
            - Return a json list  with at least one object.
            - No Returned objects in data list due only admin could see public=false.
        """
        self.client.force_authenticate(user=self.users[1])
        test_public = False
        url_endpoint = reverse(self.reverse_viewname_list) + f"?filter[public]={test_public}"

        response = self.client.get(url_endpoint)

        self.assertIn(response.headers["Content-Type"], RESPONSE_CONTENT_TYPES)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["data"])

    def test_multiple_filter(self):
        """
        Test the objects returned are filtered by mutiple attrs: rating_content and rating_instructors.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects are filtered by test_rating_content and test_rating_instructors.
        """
        test_rating_content = 2
        test_rating_instructors = test_rating_content + 1
        url_endpoint = reverse(self.reverse_viewname_list) + (
            f"?filter[rating_content]={test_rating_content}&filter[rating_instructors]={test_rating_instructors}"
        )

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        for element in response.json()["data"]:
            self.assertEqual(element["attributes"]["rating_content"], test_rating_content)
            self.assertEqual(element["attributes"]["rating_instructors"], test_rating_instructors)

    def test_sort_by_rating_content(self):
        """
        Test the objects returned are sorted by rating_content attribute.
        Expected behavior:
            - Status code 200.
            - Return a json list  with at least one object.
            - Returned objects are ordered in increase way by rating_content.
        """
        url_endpoint = reverse(self.reverse_viewname_list) + "?sort=rating_content"

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        rate = 0
        for element in response.json()["data"]:
            self.assertTrue(element["attributes"]["rating_content"] >= rate)
            rate = element["attributes"]["rating_content"]
