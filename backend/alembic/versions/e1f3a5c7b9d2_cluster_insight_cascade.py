"""add ON DELETE CASCADE to article_cluster child FKs (D33)

Enables run retention: deleting a cluster_run cascades to its clusters, and
deleting a cluster cascades to its members and insight. DDL only — this
migration deletes no rows; data pruning is handled at runtime by
clustering.pipeline.prune_old_cluster_runs (guarded, keeps the served run).

Revision ID: e1f3a5c7b9d2
Revises: c9d5e7f1a2b3
Create Date: 2026-05-29 00:00:00.000000

"""

from alembic import op

revision: str = "e1f3a5c7b9d2"
down_revision: str = "c9d5e7f1a2b3"
branch_labels = None
depends_on = None


# (constraint_name, source_table, referent_table, local_cols, remote_cols)
_FKS = [
    ("cluster_insight_cluster_id_fkey", "cluster_insight", "article_cluster", ["cluster_id"], ["id"]),
    (
        "article_cluster_member_cluster_id_fkey",
        "article_cluster_member",
        "article_cluster",
        ["cluster_id"],
        ["id"],
    ),
    ("article_cluster_run_id_fkey", "article_cluster", "cluster_run", ["run_id"], ["id"]),
    (
        "fk_article_cluster_parent_cluster_id",
        "article_cluster",
        "article_cluster",
        ["parent_cluster_id"],
        ["id"],
    ),
]


def upgrade() -> None:
    for name, src, ref, local, remote in _FKS:
        op.drop_constraint(name, src, type_="foreignkey")
        op.create_foreign_key(name, src, ref, local, remote, ondelete="CASCADE")


def downgrade() -> None:
    for name, src, ref, local, remote in _FKS:
        op.drop_constraint(name, src, type_="foreignkey")
        op.create_foreign_key(name, src, ref, local, remote)
