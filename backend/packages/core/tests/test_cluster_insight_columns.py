import uuid

from core.models import ClusterInsight


def test_cluster_insight_accepts_user_need_distribution_fields() -> None:
    ci = ClusterInsight(
        cluster_id=uuid.uuid4(),
        user_need_distribution={"Update me": 2, "Educate me": 1},
        user_need_reps_tagged=3,
    )
    assert ci.user_need_distribution == {"Update me": 2, "Educate me": 1}
    assert ci.user_need_reps_tagged == 3
