from celery import shared_task
from django.contrib.auth import get_user_model
from .models import LikeDislikeUnit, LikeDislikeCourse, FeedbackUnit, FeedbackCourse, ReportUnit, ReportCourse

User = get_user_model()


@shared_task
def persist_experience_to_db(kind, user_id, target_id, value):
    """Persist experience data to the database. This is intended to be called asynchronously after updating cache."""
    user = User.objects.get(id=user_id)
    model_map = {
        "like_unit": LikeDislikeUnit,
        "like_course": LikeDislikeCourse,
        "feedback_unit": FeedbackUnit,
        "feedback_course": FeedbackCourse,
        "report_unit": ReportUnit,
        "report_course": ReportCourse,
    }
    model = model_map.get(kind)
    if not model:
        return

    # Prepare filter and defaults based on kind
    filter_kwargs = {"author": user}
    if "unit" in kind:
        filter_kwargs["item_id"] = target_id
    else:
        filter_kwargs["course_id"] = target_id

    # Save or update
    model.objects.update_or_create(
        defaults=value,
        **filter_kwargs
    )
