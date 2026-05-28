import logging

from celery import shared_task
from .models import LikeDislikeUnit, LikeDislikeCourse, FeedbackUnit, FeedbackCourse, ReportUnit, ReportCourse

logger = logging.getLogger(__name__)


@shared_task
def persist_experience_to_db(kind, user_id, target_id, value):
    """Persist experience data to the database. This is intended to be called asynchronously after updating cache."""
    logger.info(
        f"[persist_experience_to_db] kind={kind}, user_id={user_id}, target_id={target_id}, value={value}"
    )
    model_map = {
        "LikeDislikeUnit": LikeDislikeUnit,
        "LikeDislikeCourse": LikeDislikeCourse,
        "FeedbackUnit": FeedbackUnit,
        "FeedbackCourse": FeedbackCourse,
        "ReportUnit": ReportUnit,
        "ReportCourse": ReportCourse,
    }
    model = model_map.get(kind)
    if not model:
        logger.warning(f"[persist_experience_to_db] Unknown kind: {kind}")
        return

    # Prepare filter and defaults based on kind
    filter_kwargs = {"author_id": user_id}
    if "Unit" in kind:
        filter_kwargs["item_id"] = target_id
    else:
        filter_kwargs["course_id_id"] = target_id
    value["course_id_id"] = value.pop("course_id", None)
    # Save or update
    model.objects.update_or_create(
        defaults=value,
        **filter_kwargs
    )
